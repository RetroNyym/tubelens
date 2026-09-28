"""shopping.py gelir kacagi + aksiyon reetesi testleri (ag gerektirmez)."""

from tubelens import shopping


def _video(**overrides):
    base = {
        "id": "vid1",
        "title": "En Iyi Hosting Rehberi 2026",
        "views": 100_000,
        "description": "Uzun aciklama " * 60,  # 300+ karakter
        "links": [],
        "keywords": [],
        "shopping_tags": [],
    }
    base.update(overrides)
    return base


def _analysis(**overrides):
    base = {
        "video_id": "vid1",
        "title": "En Iyi Hosting Rehberi 2026",
        "views": 100_000,
        "description_len": 100,  # kisa (varsayilan: aciklamasi eksik video)
        "link_count": 0,
        "affiliate_links": [],
        "external_links": [],
        "disclosures": [],
        "spam_signals": [],
        "topics": ["hosting"],
        "suggested_programs": ["Hostinger / VPN / Yazilim"],
        "shopping_tags": [],
        "findings": [],
        "misses": ["Affiliate link yok"],
        "opportunity_score": 0,
    }
    base.update(overrides)
    return base


def test_revenue_leak_full_miss():
    leak = shopping.revenue_leak({}, _analysis())
    # 100000 izlenme * 0.02 ctr * 3.5 $ (hosting) = 7000 $
    assert leak["potential"] == 7000.0
    assert leak["realized"] == 0.0
    assert leak["leak"] == 7000.0
    keys = [b["key"] for b in leak["breakdown"]]
    assert keys == ["affiliate", "shopping", "description"]
    assert leak["breakdown"][0]["amount"] == 4200.0  # %60
    assert leak["breakdown"][1]["amount"] == 1750.0  # %25
    assert leak["breakdown"][2]["amount"] == 700.0  # %10


def test_revenue_leak_realized_with_affiliate_and_shopping():
    leak = shopping.revenue_leak(
        {},
        _analysis(
            affiliate_links=[{"url": "https://host.io/x", "program": "Hostinger"}],
            shopping_tags=["urun1"],
            description_len=900,
        ),
    )
    # realized = %50 + %15 = %65 -> kacak = %35
    assert leak["potential"] == 7000.0
    assert leak["realized"] == 4550.0
    assert leak["leak"] == 2450.0
    assert leak["breakdown"] == []  # tum eksikler kapanmis


def test_revenue_leak_zero_views():
    leak = shopping.revenue_leak({}, _analysis(views=0))
    assert leak["leak"] == 0.0
    assert leak["potential"] == 0.0


def test_revenue_leak_default_topic_earn():
    leak = shopping.revenue_leak({}, _analysis(topics=[]))
    # default earn 1.0 -> 100000 * 0.02 * 1.0 = 2000
    assert leak["potential"] == 2000.0
    assert leak["earn_per_click"] == 1.0


def test_channel_leak_summary():
    a1 = _analysis(video_id="a", views=100_000)  # hosting -> leak 7000
    a2 = _analysis(
        video_id="b",
        views=50_000,
        topics=[],
        affiliate_links=[{"url": "x", "program": "p"}],
        shopping_tags=["t"],
        description_len=900,
    )  # default earn, gerceklesen %65 -> potential 1000, leak 350
    summary = shopping.channel_leak_summary([a1, a2])
    assert summary["total_leak"] == 7350.0
    assert summary["videos_at_risk"] == 2
    assert summary["top_leaks"][0]["video_id"] == "a"
    assert summary["top_leaks"][0]["leak"] == 7000.0


def test_action_recipe_full_miss():
    recipes = shopping.action_recipe(_video(description="kisa"), _analysis())
    ids = [r["id"] for r in recipes]
    # affiliate yok, shopping yok, aciklama kisa -> disclosure reetesi yok (aff linki yok)
    assert ids == ["affiliate", "shopping", "description"]
    by_id = {r["id"]: r for r in recipes}
    assert "Hostinger" in by_id["affiliate"]["text"]
    assert by_id["description"]["copy"].startswith("En Iyi Hosting")


def test_action_recipe_disclosure_only():
    recipes = shopping.action_recipe(
        _video(description="Uzun " * 100),
        _analysis(
            affiliate_links=[{"url": "x", "program": "p"}],
            shopping_tags=["t"],
            description_len=900,
        ),
    )
    assert [r["id"] for r in recipes] == ["disclosure"]
    assert "ortaklık" in recipes[0]["copy"]


def test_action_recipe_empty_when_complete():
    recipes = shopping.action_recipe(
        _video(description="Uzun " * 100),
        _analysis(
            affiliate_links=[{"url": "x", "program": "p"}],
            disclosures=["reklam"],
            shopping_tags=["t"],
            description_len=900,
        ),
    )
    assert recipes == []


def test_analyze_feeds_revenue_leak():
    video = _video(
        description="Kisa aciklama.",
        links=["https://www.amazon.com.tr/dp/X?tag=ornek-21"],
    )
    analysis = shopping.analyze(video)
    assert analysis["description_len"] == len("Kisa aciklama.")
    leak = shopping.revenue_leak(video, analysis)
    assert leak["leak"] > 0
    # affiliate var -> realized kismi var
    assert leak["realized"] > 0
