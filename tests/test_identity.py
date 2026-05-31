"""Tests for the Slack -> provider identity map."""
from app.config import Settings
from app.identity import IdentityMap, load_identity_map


def test_identity_map_resolves_known_user():
    m = IdentityMap(
        slack_to_jira={"U1": "557058:abc"},
        slack_to_github={"U1": "octocat"},
    )
    assert m.jira_account_id("U1") == "557058:abc"
    assert m.github_login("U1") == "octocat"


def test_identity_map_returns_none_for_unknown_or_empty():
    m = IdentityMap(slack_to_jira={"U1": "x"})
    assert m.jira_account_id("U-unknown") is None
    assert m.github_login("U1") is None  # not mapped on the github side
    assert m.jira_account_id("") is None


def test_load_identity_map_parses_json_setting():
    raw = '{"U1": {"jira": "557058:abc", "github": "octocat"}, "U2": {"github": "hubot"}}'
    m = load_identity_map(Settings(identity_map=raw))
    assert m.jira_account_id("U1") == "557058:abc"
    assert m.github_login("U1") == "octocat"
    assert m.github_login("U2") == "hubot"
    assert m.jira_account_id("U2") is None


def test_load_identity_map_empty_or_malformed_is_noop():
    assert load_identity_map(Settings(identity_map="")).jira_account_id("U1") is None
    assert load_identity_map(Settings(identity_map="not json")).github_login("U1") is None
    # A JSON value that isn't an object degrades gracefully.
    assert load_identity_map(Settings(identity_map="[1,2,3]")).github_login("U1") is None
