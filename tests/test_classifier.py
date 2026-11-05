from classifier import CATEGORIES, classify


def msg(**kw):
    base = {"folder": "inbox", "subject": "", "preview": "", "fromAddress": "someone@example.com",
            "headers": {}, "importance": "normal", "flagged": False, "focused": None}
    base.update(kw)
    return base


def test_categories():
    assert CATEGORIES == ["Priority", "Transactions", "Updates", "Promotions", "Mailing List", "Junk", "Deleted Mail"]


def test_folders_win():
    assert classify(msg(folder="junk", subject="Your receipt"))[0] == "Junk"
    assert classify(msg(folder="deleted", subject="Hi"))[0] == "Deleted Mail"


def test_rules():
    assert classify(msg(subject="Lunch tomorrow?"))[0] == "Priority"
    assert classify(msg(subject="Weekly sync", importance="high"))[0] == "Priority"
    assert classify(msg(subject="Your receipt from Uber"))[0] == "Transactions"
    assert classify(msg(subject="40% off everything", headers={"list-unsubscribe": "<https://x.com/u>"}))[0] == "Promotions"
    assert classify(msg(subject="This week in AI", headers={"list-id": "<news.x.com>"}))[0] == "Mailing List"
    assert classify(msg(subject="New sign-in to your account", fromAddress="no-reply@x.com"))[0] == "Updates"
