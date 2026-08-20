# Deterministic SQL Analytics Offloading

LLMs are notoriously prone to arithmetic hallucinations when asked to sum large lists of numbers, calculate averages, or aggregate multi-category financial expenses. J.A.R.V.I.S. eliminates arithmetic errors by offloading analytical computations directly to **PostgreSQL native aggregate queries**.

---

## 🎯 Architecture & Data Model

J.A.R.V.I.S. stores tracker items in a structured `tracker_items` PostgreSQL table with GIN-indexed `JSONB`:

```sql
CREATE TABLE tracker_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection VARCHAR(64) NOT NULL, -- "expenses", "todos", "reminders", "bookmarks"
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tracker_collection ON tracker_items(collection);
CREATE INDEX idx_tracker_data ON tracker_items USING GIN(data);
```

---

## ⚡ How Analytics Offloading Works

When the user asks:
> *"How much did I spend on groceries and dining out this month?"*

Rather than retrieving dozens of raw records and having the LLM perform mental addition, the agent invokes `query_analytics`:

```python
# Agent tool call
query_analytics(
    collection="expenses",
    aggregate_function="SUM",
    field="amount",
    filters={
        "category__in": ["groceries", "dining_out"],
        "date__gte": "2026-08-01"
    }
)
```

The backend executes a single high-speed SQL query:

```sql
SELECT 
    SUM((data->>'amount')::numeric) AS total,
    COUNT(*) AS transaction_count,
    AVG((data->>'amount')::numeric) AS average
FROM tracker_items
WHERE collection = 'expenses'
  AND data->>'category' IN ('groceries', 'dining_out')
  AND (data->>'date')::date >= '2026-08-01';
```

---

## 📊 Benefits

- **100% Deterministic Accuracy**: Zero hallucinated sums, discounts, or tax errors.
- **High Performance**: PostgreSQL processes thousands of records in sub-milliseconds using indexes.
- **Low Token Usage**: Transmits only the computed aggregate results back to the LLM context window.
