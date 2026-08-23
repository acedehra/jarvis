import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    RemoveMessage,
)
from app.services.graph import summarize_conversation, AgentState


class TestSummarizeConversation(unittest.IsolatedAsyncioTestCase):
    async def test_summarize_conversation_short_history(self):
        state: AgentState = {
            "messages": [
                HumanMessage(content="Hello", id="1"),
                AIMessage(content="Hi there!", id="2"),
            ],
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "summary": None,
        }
        result = await summarize_conversation(state)
        self.assertEqual(result, {})

    async def test_summarize_conversation_long_history(self):
        """
        Tests that summarize_conversation executes without UnboundLocalError
        and correctly generates summary and RemoveMessage instances.
        """
        messages = [
            HumanMessage(content="Add a bookmark to read later: https://example.com", id="msg-1"),
            AIMessage(content="I will save this bookmark.", id="msg-2"),
            HumanMessage(content="What's the weather in Tokyo?", id="msg-3"),
            AIMessage(content="It is sunny in Tokyo.", id="msg-4"),
            HumanMessage(content="Thanks! Can you also check London?", id="msg-5"),
            AIMessage(content="It is rainy in London.", id="msg-6"),
            HumanMessage(content="Great, what's my next task?", id="msg-7"),
            AIMessage(content="Your next task is workout.", id="msg-8"),
        ]

        state: AgentState = {
            "messages": messages,
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "summary": None,
        }

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="User saved a bookmark and asked about Tokyo/London weather."))

        with patch("app.services.graph.get_llm_model", return_value=mock_llm):
            result = await summarize_conversation(state)

        self.assertIn("summary", result)
        self.assertEqual(result["summary"], "User saved a bookmark and asked about Tokyo/London weather.")
        self.assertIn("messages", result)
        self.assertGreater(len(result["messages"]), 0)
        self.assertTrue(all(isinstance(rm, RemoveMessage) for rm in result["messages"]))
        # The IDs of removed messages should match the summarized slice
        removed_ids = [rm.id for rm in result["messages"]]
        self.assertIn("msg-1", removed_ids)
        self.assertIn("msg-2", removed_ids)

    async def test_summarize_conversation_with_existing_summary(self):
        """
        Tests consolidation when an existing summary is already in state.
        """
        messages = [
            HumanMessage(content="Msg 1", id="m1"),
            AIMessage(content="Reply 1", id="m2"),
            HumanMessage(content="Msg 2", id="m3"),
            AIMessage(content="Reply 2", id="m4"),
            HumanMessage(content="Msg 3", id="m5"),
            AIMessage(content="Reply 3", id="m6"),
            HumanMessage(content="Msg 4", id="m7"),
            AIMessage(content="Reply 4", id="m8"),
        ]

        state: AgentState = {
            "messages": messages,
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "summary": "Existing previous summary of conversation.",
        }

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Consolidated summary."))

        with patch("app.services.graph.get_llm_model", return_value=mock_llm):
            result = await summarize_conversation(state)

        self.assertEqual(result["summary"], "Consolidated summary.")
        # Verify the prompt sent to LLM included existing summary
        call_args = mock_llm.ainvoke.call_args[0][0]
        prompt_text = call_args[0].content
        self.assertIn("Here is an existing summary of the earlier conversation:", prompt_text)
        self.assertIn("Existing previous summary of conversation.", prompt_text)
