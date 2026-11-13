from app.rules.tripbrief import DayForecast, maps_links, packing_list


def test_maps_links_are_deep_links():
    l = maps_links("123 Main St, Brooklyn NY", "JFK Terminal 4")
    assert l["apple"].startswith("https://maps.apple.com/?saddr=") and "daddr=JFK+Terminal+4" in l["apple"]
    assert l["google"].startswith("https://www.google.com/maps/dir/?api=1")


def test_packing_list_reacts_to_weather():
    cold_wet = [DayForecast("2026-12-01", 2, -4, 70, 20, "Snow")]
    items = packing_list(cold_wet)
    assert "Heavy coat" in items and "Umbrella or rain shell" in items
    hot = [DayForecast("2026-07-01", 33, 24, 5, 10, "Sunny")]
    assert "Sunscreen" in packing_list(hot, flying=False)
