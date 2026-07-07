import unittest
from unittest.mock import MagicMock

from fantasy_avail.yahoo import yahoo_availability_from_hits
from fantasy_avail.yahoo import (
    AVAIL_SOURCE_FREE_AGENT,
    AVAIL_SOURCE_NA_FREE_AGENT,
    AVAIL_SOURCE_WAIVERS,
    FANTASY_AVAIL_SOURCE_KEY,
    fetch_player_ownership_batched,
    lookup_players_availability,
)


class FetchPlayerOwnershipBatchedTests(unittest.TestCase):
    def test_chunks_requests_to_yahoo_limit(self) -> None:
        league = MagicMock()
        league.ownership.side_effect = [
            {str(pid): {"ownership_type": "freeagents"} for pid in range(1, 26)},
            {str(pid): {"ownership_type": "freeagents"} for pid in range(26, 31)},
        ]

        ownership = fetch_player_ownership_batched(league, list(range(1, 31)), batch_size=25)

        self.assertEqual(len(ownership), 30)
        self.assertEqual(league.ownership.call_count, 2)
        self.assertEqual(len(league.ownership.call_args_list[0].args[0]), 25)
        self.assertEqual(len(league.ownership.call_args_list[1].args[0]), 5)


class LookupPlayersAvailabilityTests(unittest.TestCase):
    def test_marks_na_free_agents_available(self) -> None:
        league = MagicMock()
        league.player_details.return_value = [
            {
                "player_id": "60746",
                "name": {"full": "David Sandlin"},
                "position_type": "P",
                "eligible_positions": [{"position": "SP"}, {"position": "NA"}],
                "status": "NA",
            }
        ]
        league.ownership.return_value = {
            "60746": {"ownership_type": "freeagents"},
        }

        hits = lookup_players_availability(league, ["David Sandlin"])

        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].is_available)
        self.assertEqual(hits[0].availability, AVAIL_SOURCE_NA_FREE_AGENT)
        self.assertEqual(hits[0].yahoo_player["status"], "NA")


class YahooAvailabilityFromHitsTests(unittest.TestCase):
    def test_reports_na_free_agent(self) -> None:
        hits = [
            {
                FANTASY_AVAIL_SOURCE_KEY: AVAIL_SOURCE_NA_FREE_AGENT,
                "status": "NA",
            }
        ]
        self.assertEqual(yahoo_availability_from_hits(hits), AVAIL_SOURCE_NA_FREE_AGENT)

    def test_prefers_waivers_over_na(self) -> None:
        hits = [
            {
                FANTASY_AVAIL_SOURCE_KEY: AVAIL_SOURCE_WAIVERS,
                "status": "",
            }
        ]
        self.assertEqual(yahoo_availability_from_hits(hits), AVAIL_SOURCE_WAIVERS)

    def test_defaults_to_free_agent(self) -> None:
        hits = [{FANTASY_AVAIL_SOURCE_KEY: AVAIL_SOURCE_FREE_AGENT, "status": ""}]
        self.assertEqual(yahoo_availability_from_hits(hits), AVAIL_SOURCE_FREE_AGENT)


if __name__ == "__main__":
    unittest.main()
