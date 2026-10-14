# Golden evaluation set

The set is being built across several ingestion outcomes. Counts below show
the current number of JSON cases and the planned target for each category.

| Current / target | Type | Tests | Coverage |
|---:|---|---|---|
| 5 / 5 | Full ingredient list in the description | `description` rung (`description_list`, `video_description`) | Ingredients and quantities available directly in the YouTube description |
| 5 / 5 | Description links to a recipe blog | `linked_recipe` rung | Recipe titles, measured ingredients, preparation details, and grouped components |
| 0 / 4 | Recipe only spoken, vague description | `partial` rung / gaps | Recoverable spoken ingredients alongside missing or uncertain details |
| 0 / 2 | Vague amounts (for example, “a splash” or “some butter”) | `qualitative` handling | Ingredients with non-numeric or imprecise quantities |
| 0 / 4 | Not a recipe | `not_a_recipe` exit | Videos such as restaurant reviews, kitchen gadget reviews, or food vlogs |

## Cases

| Video | Type | Recipe | Coverage notes |
|---|---|---|---|
| [EY7jt2DKe38](https://www.youtube.com/watch?v=EY7jt2DKe38) ([JSON](./EY7jt2DKe38.json)) | `description` | Lebanese Lemon Garlic Chicken (Al Aseel restaurant copycat) | Ingredients and amounts extracted from the video description |
| [41Kt91N4K34](https://www.youtube.com/watch?v=41Kt91N4K34) ([JSON](./41Kt91N4K34.json)) | `description` | The Best Chicken Pie You'll Ever Make | Fallow chicken pie ingredients and quantities extracted from the video description |
| [OuTIFqKSsN8](https://www.youtube.com/watch?v=OuTIFqKSsN8) ([JSON](./OuTIFqKSsN8.json)) | `description` | Crispy and juicy chicken KARAAGE. Best recipe and method. | Description ingredient list with measured chicken and marinade components |
| [y1OOyhQ2DTo](https://www.youtube.com/watch?v=y1OOyhQ2DTo) ([JSON](./y1OOyhQ2DTo.json)) | `description` | Authentic Chicken Biryani (30 Minute vs 3 Hour) | Full ingredient lists for both preparation versions |
| [6XlMguO9r-M](https://www.youtube.com/watch?v=6XlMguO9r-M) ([JSON](./6XlMguO9r-M.json)) | `description` | Hyderabadi Chicken Biryani | Ingredients and amounts extracted from the video description |
| [63tRWpVKKG8](https://www.youtube.com/watch?v=63tRWpVKKG8) ([JSON](./63tRWpVKKG8.json)) | `linked_recipe` | Massaman Chicken Curry | Hot Thai Kitchen recipe with chicken, curry paste, and sauce components; ranges and metric conversions |
| [MuYIq9V1OHg](https://www.youtube.com/watch?v=MuYIq9V1OHg) ([JSON](./MuYIq9V1OHg.json)) | `linked_recipe` | Chinese Takeaway Fried Rice | Andy Cooks recipe with preparation details and measured ingredients |
| [jDsO3J5klWg](https://www.youtube.com/watch?v=jDsO3J5klWg) ([JSON](./jDsO3J5klWg.json)) | `linked_recipe` | Kerala Style Chicken Curry without coconut (Nadan kozhi curry) | Recipe components for marinade, curry, and garnish; includes “salt to taste” |
| [qEHvmINXUfk](https://www.youtube.com/watch?v=qEHvmINXUfk) ([JSON](./qEHvmINXUfk.json)) | `linked_recipe` | The Best Fried Chicken at Home | Joshua Weissman recipe with marinade and dredge components; includes metric weights |
| [yvfVAvJZ-8A](https://www.youtube.com/watch?v=yvfVAvJZ-8A) ([JSON](./yvfVAvJZ-8A.json)) | `linked_recipe` | The Best Burger Buns Ever | Joshua Weissman recipe with dough, wash/finish, and optional toppings |

Current total: 10 cases. Planned total: 20 cases.
