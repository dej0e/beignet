# Golden evaluation set

The set is being built across several ingestion outcomes. Counts below show
the current number of JSON cases and the planned target for each category.

| Current / target | Type | Tests | Coverage |
|---:|---|---|---|
| 0 / 5 | Full ingredient list in the description | `description` rung | Ingredients and quantities available directly in the YouTube description |
| 4 / 5 | Description links to a recipe blog | `linked_recipe` rung | Recipe titles, measured ingredients, preparation details, and grouped components |
| 0 / 4 | Recipe only spoken, vague description | `partial` rung / gaps | Recoverable spoken ingredients alongside missing or uncertain details |
| 0 / 2 | Vague amounts (for example, “a splash” or “some butter”) | `qualitative` handling | Ingredients with non-numeric or imprecise quantities |
| 0 / 4 | Not a recipe | `not_a_recipe` exit | Videos such as restaurant reviews, kitchen gadget reviews, or food vlogs |

## Cases

| Video | Type | Recipe | Coverage notes |
|---|---|---|---|
| [63tRWpVKKG8](https://www.youtube.com/watch?v=63tRWpVKKG8) ([JSON](./63tRWpVKKG8.json)) | `linked_recipe` | Massaman Chicken Curry | Hot Thai Kitchen recipe with chicken, curry paste, and sauce components; ranges and metric conversions |
| [MuYIq9V1OHg](https://www.youtube.com/watch?v=MuYIq9V1OHg) ([JSON](./MuYIq9V1OHg.json)) | `linked_recipe` | Chinese Takeaway Fried Rice | Andy Cooks recipe with preparation details and measured ingredients |
| [jDsO3J5klWg](https://www.youtube.com/watch?v=jDsO3J5klWg) ([JSON](./jDsO3J5klWg.json)) | `linked_recipe` | Kerala Style Chicken Curry without coconut (Nadan kozhi curry) | Recipe components for marinade, curry, and garnish; includes “salt to taste” |
| [qEHvmINXUfk](https://www.youtube.com/watch?v=qEHvmINXUfk) ([JSON](./qEHvmINXUfk.json)) | `linked_recipe` | The Best Fried Chicken at Home | Joshua Weissman recipe with marinade and dredge components; includes metric weights |

Current total: 4 cases. Planned total: 20 cases.
