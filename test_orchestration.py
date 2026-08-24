"""Offline tests for the orchestration and minimal Telegram bot."""

import unittest
from unittest.mock import Mock, patch

import bot
import processQuery


class OrchestrationTests(unittest.TestCase):
    def test_code_route_matches_notebook_pipeline(self):
        replies = iter((
            (
                "CODE_REQUIRED: Write Python that counts lowercase r in "
                "the word strawberry and prints the result.",
                {"total_tokens": 10},
            ),
            ("print('strawberry'.count('r'))", {"total_tokens": 8}),
            ("There are 3 r's in strawberry.", {"total_tokens": 7}),
        ))

        with (
            patch.object(processQuery, "make_client", return_value=Mock()),
            patch.object(processQuery, "_chat", side_effect=lambda *_: next(replies)),
            patch.object(
                processQuery,
                "run_python_script",
                return_value="[SUCCESS] Output:\n3\n",
            ),
        ):
            answer, audit = processQuery.process_query(
                "how many r's are in strawberry"
            )

        self.assertEqual(answer, "There are 3 r's in strawberry.")
        self.assertEqual(audit[0]["route"], processQuery.Route.CODE.value)

    def test_direct_answer_comes_from_orchestrator(self):
        with (
            patch.object(processQuery, "make_client", return_value=Mock()),
            patch.object(
                processQuery,
                "_chat",
                return_value=("DIRECT: Photosynthesis uses light.", None),
            ) as chat,
        ):
            answer, audit = processQuery.process_query("Explain photosynthesis")

        self.assertEqual(answer, "Photosynthesis uses light.")
        self.assertEqual(audit[0]["route"], processQuery.Route.DIRECT.value)
        chat.assert_called_once()


class TelegramBotTests(unittest.TestCase):
    def test_add_memory(self):
        query = bot.add_memory(
            "What is it called?",
            [("My project is Moss.", "Understood.")],
        )

        self.assertIn("User: My project is Moss.", query)
        self.assertTrue(query.endswith("New message:\nWhat is it called?"))

    def test_polling_memory_reset_and_replies(self):
        messages = [
            (1, "/start"),
            (1, "one"),
            (1, "two"),
            (1, "three"),
            (1, "four"),
            (1, "five"),
            (2, "other chat"),
            (1, "/reset"),
            (1, "after reset"),
        ]
        get_updates = Mock()
        get_updates.json.return_value = {
            "result": [
                {
                    "update_id": number,
                    "message": {"chat": {"id": chat_id}, "text": text},
                }
                for number, (chat_id, text) in enumerate(messages)
            ]
        }
        no_updates = Mock()
        no_updates.json.return_value = {"result": []}
        sent = Mock()

        with (
            patch.object(
                bot.requests,
                "get",
                side_effect=[get_updates, no_updates, KeyboardInterrupt],
            ) as get,
            patch.object(bot.requests, "post", return_value=sent) as post,
            patch.object(
                bot,
                "process_query",
                side_effect=lambda query: (
                    f"Answer to {query.splitlines()[-1]}",
                    [{"route": "DIRECT"}],
                ),
            ) as process,
            self.assertRaises(KeyboardInterrupt),
        ):
            bot.run_bot("test-token")

        # Only the latest three earlier turns reach the fifth question.
        fifth_query = process.call_args_list[4].args[0]
        self.assertNotIn("User: one", fifth_query)
        self.assertIn("User: two", fifth_query)
        self.assertIn("User: four", fifth_query)

        # Chats have separate memory, and /reset removes chat 1's memory.
        self.assertEqual(process.call_args_list[5].args[0], "other chat")
        self.assertEqual(process.call_args_list[6].args[0], "after reset")

        # /start and /reset are local, so seven of nine messages call the AI.
        self.assertEqual(process.call_count, 7)
        self.assertEqual(post.call_count, 9)
        start_reply = post.call_args_list[0].kwargs["json"]["text"]
        reset_reply = post.call_args_list[7].kwargs["json"]["text"]
        self.assertIn("Routed to: Bot command", start_reply)
        self.assertIn("Routed to: Bot command", reset_reply)
        self.assertEqual(get.call_args_list[1].kwargs["params"]["offset"], 9)
        get_updates.raise_for_status.assert_called_once()
        no_updates.raise_for_status.assert_called_once()
        sent.raise_for_status.assert_called()


if __name__ == "__main__":
    unittest.main()
