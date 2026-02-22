"""Chess.com public API client.

Provides a single, tested point of access for all Chess.com public API
endpoints used by the codebase.  All HTTP calls should route through
:class:`ChessComClient` so that the base URL, authentication headers, and
retry behaviour are managed in one place.
"""

from __future__ import annotations

import time

import requests

BASE_URL = "https://api.chess.com/pub"

# Chrome user-agent keeps requests below the radar :)
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    )
}


class ChessComClient:
    """Single point of access for the Chess.com public API.

    All HTTP calls in the codebase should eventually route through this
    client so that the base URL, headers, and retry behaviour are managed
    in one place.

    Args:
        base_url: Root of the Chess.com public API.  Defaults to the live
            production URL; override in tests to point at a mock server.
        headers: HTTP request headers.  Defaults to a Chrome user-agent.
        retries: Total number of attempts before propagating an exception.
        backoff_factor: Multiplier for exponential back-off between retries.
            Delay after attempt *n* is ``backoff_factor * 2 ** n`` seconds.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        headers: dict[str, str] | None = None,
        retries: int = 3,
        backoff_factor: float = 0.3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers if headers is not None else DEFAULT_HEADERS.copy()
        self.retries = retries
        self.backoff_factor = backoff_factor

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint: str) -> dict:
        """Perform a GET request with exponential back-off retry.

        Args:
            endpoint: Path relative to *base_url* (leading slash optional),
                **or** a fully-qualified URL.  Fully-qualified URLs are used
                when Chess.com embeds the match URL directly inside a
                club-matches response.

        Returns:
            Parsed JSON body as a ``dict``.

        Raises:
            requests.HTTPError: When all retry attempts are exhausted.
            requests.ConnectionError: On unrecoverable connection failures.
            requests.Timeout: When all retry attempts time out.
        """
        url = (
            endpoint
            if endpoint.startswith("http")
            else f"{self.base_url}/{endpoint.lstrip('/')}"
        )

        for attempt in range(self.retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                return response.json()
            except (ConnectionError, requests.HTTPError, requests.Timeout) as exc:
                if attempt < self.retries - 1:
                    time.sleep(self.backoff_factor * (2**attempt))
                else:
                    raise exc

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_club_members(self, club_ref: str) -> list[dict]:
        """Return all members of a club, merging the three activity groups.

        Chess.com splits members into ``weekly``, ``monthly``, and
        ``all_time`` activity buckets.  This method merges them into a
        single flat list so callers do not need to know about the
        bucketing.

        Args:
            club_ref: Club identifier, e.g. ``"team-scotland"``.

        Returns:
            Flat list of member dicts as returned by the Chess.com API.
        """
        data = self._get(f"club/{club_ref}/members")
        return (
            data.get("weekly", [])
            + data.get("monthly", [])
            + data.get("all_time", [])
        )

    def get_player_stats(self, username: str) -> dict:
        """Return raw stats for *username*.

        The response contains per-variant statistics including current
        rating, record (wins/losses/draws/timeouts), and timeout
        percentage.

        Args:
            username: Chess.com username (case-insensitive).

        Returns:
            Stats dict keyed by variant (e.g. ``chess_daily``,
            ``chess960_daily``).  Returns an empty dict if the player
            has never played any games.
        """
        return self._get(f"player/{username}/stats")

    def get_player_profile(self, username: str) -> dict:
        """Return the public profile for *username*.

        Args:
            username: Chess.com username.

        Returns:
            Profile dict containing ``name``, ``title``, ``last_online``,
            ``joined``, and other public fields.
        """
        return self._get(f"player/{username}")

    def get_club_matches(self, club_ref: str) -> dict:
        """Return the full matches payload for a club.

        Args:
            club_ref: Club identifier.

        Returns:
            Dict with keys ``finished``, ``in_progress``, and
            ``registered``, each containing a list of match summary dicts.
        """
        return self._get(f"club/{club_ref}/matches")

    def get_match(self, match_id_or_url: str) -> dict:
        """Return match detail for *match_id_or_url*.

        Accepts either a bare match ID (e.g. ``"12345"``) or the full URL
        that Chess.com embeds inside club-matches responses (e.g.
        ``"https://api.chess.com/pub/match/12345"``).

        Args:
            match_id_or_url: Bare match ID string **or** a fully-qualified
                match URL.

        Returns:
            Match detail dict containing ``settings``, ``teams``, and
            per-player results.
        """
        return self._get(
            match_id_or_url
            if match_id_or_url.startswith("http")
            else f"match/{match_id_or_url}"
        )
