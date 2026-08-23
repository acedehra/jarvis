import unittest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.services.graph import sanitize_messages_for_llm
from langchain_google_genai.chat_models import _parse_chat_history

class TestMessageSanitizer(unittest.TestCase):
    def test_interrupted_tool_call_without_response(self):
        """
        Tests that an interrupted tool call (no ToolMessage) is converted so that
        the subsequent turn does not violate the Gemini function call order rule.
        """
        raw_messages = [
            SystemMessage(content="You are J.A.R.V.I.S."),
            HumanMessage(content="Send a message on Telegram"),
            AIMessage(content="", tool_calls=[{"id": "call_1", "name": "send_telegram_message", "args": {"message": "hi"}}]),
            HumanMessage(content="Actually, check the weather instead"),
        ]
        
        sanitized = sanitize_messages_for_llm(raw_messages)
        sys_inst, parsed_turns = _parse_chat_history(sanitized, model="gemini-3.1-flash-lite")
        
        # Must have valid turns without raw dangling FunctionCall
        self.assertIsNotNone(sys_inst)
        self.assertGreater(len(parsed_turns), 0)
        # Verify no unresponded function call turn precedes the last human message
        roles = [turn.role for turn in parsed_turns]
        self.assertEqual(roles, ["user", "model", "user"])

    def test_history_starting_with_tool_call_or_tool_message(self):
        """
        Tests that conversation history starting with an AIMessage or ToolMessage
        is prepended with a user turn so function call turn comes after a user turn.
        """
        raw_messages = [
            SystemMessage(content="You are J.A.R.V.I.S."),
            AIMessage(content="", tool_calls=[{"id": "call_2", "name": "get_weather", "args": {"city": "Paris"}}]),
            ToolMessage(content="15C Rainy", tool_call_id="call_2", name="get_weather"),
            AIMessage(content="It is 15C and rainy in Paris."),
            HumanMessage(content="Thanks!"),
        ]
        
        sanitized = sanitize_messages_for_llm(raw_messages)
        sys_inst, parsed_turns = _parse_chat_history(sanitized, model="gemini-3.1-flash-lite")
        
        self.assertIsNotNone(sys_inst)
        self.assertEqual(parsed_turns[0].role, "user")
        self.assertEqual(parsed_turns[1].role, "model")
        self.assertEqual(parsed_turns[2].role, "user") # Function response

    def test_orphaned_tool_messages_removed(self):
        """
        Tests that orphaned ToolMessages (with no preceding AIMessage) are cleanly dropped.
        """
        raw_messages = [
            SystemMessage(content="You are J.A.R.V.I.S."),
            ToolMessage(content="Orphan result", tool_call_id="nonexistent_id", name="some_tool"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hello Sir!"),
        ]
        
        sanitized = sanitize_messages_for_llm(raw_messages)
        sys_inst, parsed_turns = _parse_chat_history(sanitized, model="gemini-3.1-flash-lite")
        
        self.assertEqual([t.role for t in parsed_turns], ["user", "model"])

    def test_consecutive_ai_messages_with_tool_call(self):
        """
        Tests that if an AIMessage with tool_calls follows an AIMessage (text),
        a bridging user turn is added so function call is immediately after a user turn.
        """
        raw_messages = [
            SystemMessage(content="You are J.A.R.V.I.S."),
            HumanMessage(content="Hello"),
            AIMessage(content="Greetings Sir."),
            AIMessage(content="", tool_calls=[{"id": "call_3", "name": "get_weather", "args": {"city": "London"}}]),
            ToolMessage(content="10C Cloudy", tool_call_id="call_3", name="get_weather"),
            AIMessage(content="It is 10C and cloudy in London."),
            HumanMessage(content="Thank you."),
        ]
        
        sanitized = sanitize_messages_for_llm(raw_messages)
        sys_inst, parsed_turns = _parse_chat_history(sanitized, model="gemini-3.1-flash-lite")
        
        # Turn sequence must be valid for Gemini
        for i, turn in enumerate(parsed_turns):
            if any(p.function_call for p in turn.parts):
                # Turn before this MUST be user or function response
                prev_turn = parsed_turns[i-1]
                self.assertEqual(prev_turn.role, "user")

    def test_partial_tool_response_resolution(self):
        """
        Tests that if an AIMessage requested 2 tools but only 1 has a response in history,
        only the answered tool call is retained so no empty function responses occur.
        """
        raw_messages = [
            SystemMessage(content="You are J.A.R.V.I.S."),
            HumanMessage(content="Check weather and query notes"),
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "get_weather", "args": {"city": "Tokyo"}},
                {"id": "c2", "name": "query_records", "args": {"collection": "notes"}}
            ]),
            ToolMessage(content="22C Clear", tool_call_id="c1", name="get_weather"),
            HumanMessage(content="Next command"),
        ]
        
        sanitized = sanitize_messages_for_llm(raw_messages)
        sys_inst, parsed_turns = _parse_chat_history(sanitized, model="gemini-3.1-flash-lite")
        
        self.assertIsNotNone(sys_inst)
        self.assertEqual(parsed_turns[0].role, "user")

if __name__ == "__main__":
    unittest.main()
