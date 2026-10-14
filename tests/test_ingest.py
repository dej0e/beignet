import pytest

from beignet.ingest import description_ingredients, ingredients_from_html, is_ingredient_line


@pytest.mark.parametrize("line", [
    "2 cloves garlic", "1/2 tsp salt", "1 1/2 tbsp lemon juice", "1 ½ cups water", "½ cup peas",
    "200g flour", "5 to 6 tablespoons paste", "- 3 large red onions", "▢ 1 kg chicken",
    "Soy sauce 25 grams", "Chicken 250~350 grams",
])
def test_ingredient_lines(line):
    assert is_ingredient_line(line)


@pytest.mark.parametrize("line", [
    "1. Set your oven to 190C", "00:55 make the marinade sauce", "Salt to taste", "LEMON GARLIC MARINADE:",
])
def test_non_ingredient_lines(line):
    assert not is_ingredient_line(line)


def test_description_span_keeps_headings_and_amountless_lines():
    description = "\n".join([
        "Intro paragraph about the dish.", "", "MARINADE:", "2 tbsp yogurt", "1 1/2 tbsp lemon juice",
        "1 tsp salt", "Lemon wedges, for garnish", "", "1. Mix everything.",
        "Lots of later chatter", "More chatter", "Even more chatter", "Subscribe!",
    ])
    span = description_ingredients(description).splitlines()
    assert "MARINADE:" in span
    assert "1 1/2 tbsp lemon juice" in span
    assert "Lemon wedges, for garnish" in span
    assert "Subscribe!" not in span


def test_description_without_list():
    assert description_ingredients("Just a vlog.\nNo recipe here.\n1. Watch") is None


def test_html_section_prefers_recipe_card_and_keeps_groups():
    page = """
    <h2>Ingredients and Notes</h2><p>Chicken thighs are best. Coconut milk matters.</p>
    <h2>Instructions</h2><p>Cook it.</p>
    <h3>Ingredients</h3>
    <ul><li>2 cups coconut milk</li><li>3 tbsp fish sauce</li></ul>
    <h4>Curry Paste</h4>
    <ul><li>▢ 5 pc whole cloves</li><li>1 tsp cumin seeds</li></ul>
    <h3>Instructions</h3><p>Simmer 35 minutes.</p>
    """
    assert ingredients_from_html(page) == [
        "2 cups coconut milk", "3 tbsp fish sauce", "Curry Paste", "5 pc whole cloves", "1 tsp cumin seeds",
    ]
