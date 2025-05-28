# Kali Fit - Recipe Builder

A system for managing and normalizing ingredient data for recipes.

## Features

- Ingredient name normalization and grouping
- Multi-language support (English, Russian, Spanish, Hebrew)
- Nutrition data management
- Category management
- Data export to CSV

## Project Structure

```
backend/
├── data_maker/
│   └── receipe_builder/
│       ├── ingredient_normalizer.py  # Handles ingredient name normalization
│       ├── ingredient_utils.py       # Utility functions for ingredient data
│       └── mongo_handler.py         # MongoDB connection and operations
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with MongoDB credentials:
```
MONGO_INITDB_ROOT_USERNAME=your_username
MONGO_INITDB_ROOT_PASSWORD=your_password
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=recipe_db_v3
```

3. Run the normalizer:
```bash
python backend/data_maker/receipe_builder/ingredient_normalizer.py
```

## Data Structure

The system uses three main MongoDB collections:
- `ingredient_names_v3`: Original ingredient names
- `ingredients_nutrition_v3`: Nutrition data
- `ingredient_categories_v3`: Ingredient categories
- `normalized_ingredients_v1`: Normalized and grouped ingredients

## Usage

1. Normalize ingredients:
```python
from backend.data_maker.receipe_builder.ingredient_normalizer import create_normalized_collection
create_normalized_collection()
```

2. Get ingredient data:
```python
from backend.data_maker.receipe_builder.ingredient_utils import get_ingredients_dataframe
df = get_ingredients_dataframe()
```

3. Save to CSV:
```python
from backend.data_maker.receipe_builder.ingredient_utils import save_ingredients_to_csv
save_ingredients_to_csv(df, "ingredients_data.csv")
``` 