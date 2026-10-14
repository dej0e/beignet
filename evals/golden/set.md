# Golden evaluation set

The set is being built across several ingestion outcomes. Counts below show
the current number of JSON cases and the planned target for each category.

| Current / target | Type | Tests | Coverage |
|---:|---|---|---|
| 5 / 5 | Full ingredient list in the description | `description` rung | Ingredients and quantities available directly in the YouTube description |
| 5 / 5 | Description links to a recipe blog | `linked_recipe` rung | Recipe titles, measured ingredients, preparation details, and grouped components |
| 0 / 4 | Recipe only spoken, vague description | `partial` rung / gaps | Recoverable spoken ingredients alongside missing or uncertain details |
| 0 / 2 | Vague amounts (for example, “a splash” or “some butter”) | `qualitative` handling | Ingredients with non-numeric or imprecise quantities |
| 0 / 4 | Not a recipe | `not_a_recipe` exit | Videos such as restaurant reviews, kitchen gadget reviews, or food vlogs |

## Labeling conventions

Labels are written by hand from the source text the ingest step returns (description span or the
linked page's ingredient section), not from other versions of the recipe.

- Every ingredient line is labeled, including lines without amounts ("Salt to taste", "Puff pastry").
  A line naming several items ("Cilantro, mint, lemon juice to garnish") gives one entry per item,
  all with the same `raw_text`.
- Headings, instructions, and lines that only refer back to earlier ingredients are not labeled.
  Headings become `component`.
- `raw_text` is the source line verbatim (whitespace collapsed).
- `name`: shoppable item; "X or Y" takes the first option.
- Units are never converted. When a line gives two amounts the first wins:
  "2 cups (480mL)" -> 2 cup, "500g/ 1lb" -> 500 g.
- Countable whole items are `each` ("3 numbers onion", "5-7 pods green cardamom").
  Units outside the `Unit` enum keep the number with `unit: null` and the word in `qualitative`
  ("3 thyme sprigs" -> 3, "sprigs").
- `servings` is null unless the text states it.

## Cases

| Video | Type | Recipe | Coverage notes |
|---|---|---|---|
| [EY7jt2DKe38](https://www.youtube.com/watch?v=EY7jt2DKe38) ([JSON](./EY7jt2DKe38.json)) | `description` | Lebanese Lemon Garlic Chicken (Al Aseel restaurant copycat) | Marinade, yogurt sauce, and serving groups; mixed fraction (1 1/2 tbsp); split garnish line |
| [41Kt91N4K34](https://www.youtube.com/watch?v=41Kt91N4K34) ([JSON](./41Kt91N4K34.json)) | `description` | The Best Chicken Pie You'll Ever Make | Pie filling and chicken supreme sauce lists from the description; amount-less lines (puff pastry, butter) |
| [OuTIFqKSsN8](https://www.youtube.com/watch?v=OuTIFqKSsN8) ([JSON](./OuTIFqKSsN8.json)) | `description` | Crispy and juicy chicken KARAAGE. Best recipe and method. | Name-then-amount lines ("Soy sauce 25 grams"); a 250~350 g range; no section headings |
| [y1OOyhQ2DTo](https://www.youtube.com/watch?v=y1OOyhQ2DTo) ([JSON](./y1OOyhQ2DTo.json)) | `description` | Authentic Chicken Biryani (30 Minute vs 3 Hour) | Both 30 minute and 3 hour versions, masala and saffron milk sub-lists; multi-item garnish line split |
| [6XlMguO9r-M](https://www.youtube.com/watch?v=6XlMguO9r-M) ([JSON](./6XlMguO9r-M.json)) | `description` | Hyderabadi Chicken Biryani | Ingredients and amounts extracted from the video description |
| [63tRWpVKKG8](https://www.youtube.com/watch?v=63tRWpVKKG8) ([JSON](./63tRWpVKKG8.json)) | `linked_recipe` | Massaman Chicken Curry | Hot Thai Kitchen recipe card incl. Quick Massaman Curry Paste sub-recipe; ranges; metric equivalents ignored |
| [MuYIq9V1OHg](https://www.youtube.com/watch?v=MuYIq9V1OHg) ([JSON](./MuYIq9V1OHg.json)) | `linked_recipe` | Chinese Takeaway Fried Rice | Andy Cooks recipe with preparation details and measured ingredients |
| [jDsO3J5klWg](https://www.youtube.com/watch?v=jDsO3J5klWg) ([JSON](./jDsO3J5klWg.json)) | `linked_recipe` | Kerala Style Chicken Curry without coconut (Nadan kozhi curry) | Marination and masala gravy groups; "3 numbers" counts; curry-leaf sprigs; bare "salt" line |
| [qEHvmINXUfk](https://www.youtube.com/watch?v=qEHvmINXUfk) ([JSON](./qEHvmINXUfk.json)) | `linked_recipe` | The Best Fried Chicken at Home | Marinade and dredge groups; every line has a metric equivalent in parentheses (ignored) |
| [yvfVAvJZ-8A](https://www.youtube.com/watch?v=yvfVAvJZ-8A) ([JSON](./yvfVAvJZ-8A.json)) | `linked_recipe` | The Best Burger Buns Ever | Potato and dough groups; gram amounts; optional amylase |

Current total: 10 cases. Planned total: 20 cases.
