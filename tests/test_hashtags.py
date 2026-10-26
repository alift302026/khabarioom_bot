"""Tests for hashtag selection."""

from hashtags import DEFAULT_HASHTAGS, make_hashtags


def test_two_keyword_matches():
    tags = make_hashtags("تحریم جدید علیه ایران", "متن خبر")
    # MAP order puts ایران before تحریم
    assert tags == "#ایران #تحریم"


def test_no_match_returns_default_pair():
    assert make_hashtags("خبر ورزشی اروپا", "بازی فوتبال") == DEFAULT_HASHTAGS


def test_single_match_gets_second_default_tag():
    assert make_hashtags("قیمت دلار", "بازار ارز") == "#دلار #خبر"


def test_at_most_two_tags():
    tags = make_hashtags("جنگ در غزه و تحریم آمریکا و نفت و بورس", "دولت و مجلس")
    assert len(tags.split()) == 2


def test_empty_inputs_do_not_crash():
    assert make_hashtags("", "") == DEFAULT_HASHTAGS
