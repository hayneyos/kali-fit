from urllib.parse import quote_plus

import pandas as pd
from typing import Dict, List, Optional, Tuple
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
from difflib import SequenceMatcher
import re
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from functools import partial
import numpy as np
from tqdm import tqdm

from backend.data_maker.receipe_builder.mongo_handler import ingredient_names_collection, \
    normalized_ingredients_collection, client, ingredients_nutrition_collection

# Load environment variables
load_dotenv()




def clean_text(text: str, remove_common_words: bool = True) -> str:
    """
    Clean and normalize text by:
    1. Converting to lowercase
    2. Removing special characters
    3. Removing numbers and units
    4. Optionally removing common words
    """
    if not isinstance(text, str):
        return ""
        
    # Convert to lowercase
    text = text.lower()
    
    # Remove numbers and units
    text = re.sub(r'\d+(?:\s*\/\s*\d+)?\s*(?:ounce|oz|g|kg|ml|l|sliced|slice|tablespoons|tablespoon|cups|cup|tbsp|tsp|pieces|piece|cans|can|packs|pack|chunks|chunk|)?', '', text)
    
    # Remove special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Remove extra spaces
    text = ' '.join(text.split())
    
    if remove_common_words:
        # Remove common words
        common_words = ['fresh', 'frozen', 'canned', 'dried', 'raw', 'cooked', 'boiled', 'baked', 'grilled']
        words = text.split()
        words = [w for w in words if w not in common_words]
        text = ' '.join(words)
    
    return text.strip()

def fast_similarity(str1: str, str2: str) -> float:
    """
    A faster similarity calculation that uses length difference as an early stopping criterion
    """
    if not str1 or not str2:
        return 0.0
        
    # Early stopping based on length difference
    len1, len2 = len(str1), len(str2)
    if abs(len1 - len2) > min(len1, len2) * 0.5:  # If length difference is more than 50%
        return 0.0
        
    # Use SequenceMatcher for actual comparison
    return SequenceMatcher(None, str1, str2).ratio()

def process_batch(batch_data: List[Dict], similarity_threshold: float = 0.8) -> Dict[str, List[Dict]]:
    """
    Process a batch of ingredients to find similar names
    """
    groups = defaultdict(list)
    processed = set()
    
    for i, doc1 in enumerate(batch_data):
        if i in processed:
            continue
            
        current_group = [doc1]
        processed.add(i)
        
        # Compare with remaining documents
        for j, doc2 in enumerate(batch_data[i+1:], i+1):
            if j in processed:
                continue
                
            similarity = fast_similarity(
                doc1['cleaned_primary'],
                doc2['cleaned_primary']
            )
            
            if similarity >= similarity_threshold:
                current_group.append(doc2)
                processed.add(j)
        
        if current_group:
            group_key = min(current_group, key=lambda x: len(x['primary_name']))['primary_name']
            groups[group_key].extend(current_group)
    
    return dict(groups)

def find_similar_names(names_data: List[Dict], similarity_threshold: float = 0.8, batch_size: int = 1000) -> Dict[str, List[Dict]]:
    """
    Group similar ingredient names together based on similarity threshold using parallel processing
    """
    print("Cleaning and preparing data...")
    # First, clean all names
    cleaned_data = []
    for doc in tqdm(names_data, desc="Cleaning names"):
        cleaned_doc = doc.copy()
        cleaned_doc['cleaned_names'] = {}
        
        # Clean primary name (with common words removal for similarity comparison)
        cleaned_doc['cleaned_primary'] = clean_text(doc['primary_name'], remove_common_words=True)
        
        # Clean names in each language (with common words removal for similarity comparison)
        for lang in ['english', 'russian', 'spanish', 'hebrew']:
            if lang in doc['names']:
                name = doc['names'][lang]['name']
                cleaned_doc['cleaned_names'][lang] = clean_text(name, remove_common_words=True)
        
        cleaned_data.append(cleaned_doc)
    
    print("Processing batches in parallel...")
    # Split data into batches
    batches = [cleaned_data[i:i + batch_size] for i in range(0, len(cleaned_data), batch_size)]
    
    # Process batches in parallel
    num_processes = max(1, cpu_count() - 1)  # Leave one CPU free
    with Pool(processes=num_processes) as pool:
        process_func = partial(process_batch, similarity_threshold=similarity_threshold)
        batch_results = list(tqdm(
            pool.imap(process_func, batches),
            total=len(batches),
            desc="Processing batches"
        ))
    
    # Merge results from all batches
    final_groups = defaultdict(list)
    for batch_group in batch_results:
        for key, items in batch_group.items():
            final_groups[key].extend(items)
    
    return dict(final_groups)

def create_normalized_collection():
    """
    Create a new collection with normalized ingredient groups
    """
    try:
        print("Fetching data from MongoDB...")
        # Get all documents from ingredient_names collection
        names_data = list(ingredient_names_collection.find({}))
        print(f"Found {len(names_data)} ingredients to process")
        
        # Get nutrition data for matching
        nutrition_data = list(ingredients_nutrition_collection.find({}))
        nutrition_dict = {str(doc['ingredient_names_id']): doc for doc in nutrition_data}
        
        # Find similar names and group them
        # grouped_names = find_similar_names(names_data[:100])
        grouped_names = find_similar_names(names_data)
        
        print("Creating normalized collection...")
        # Create new documents for the normalized collection
        normalized_docs = []
        for group_key, group_items in tqdm(grouped_names.items(), desc="Creating documents"):
            # Clean the group key (primary name) without removing common words
            cleaned_primary_name = clean_text(group_key, remove_common_words=False)
            
            # Create a new document for the group
            group_doc = {
                'primary_name': cleaned_primary_name,
                'variations': [],
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
            
            # Add all variations
            for item in group_items:
                # Clean the original name without removing common words
                cleaned_original_name = clean_text(item['primary_name'], remove_common_words=False)
                
                # Clean English name in the names dictionary without removing common words
                cleaned_names = item['names'].copy()
                if 'english' in cleaned_names:
                    cleaned_names['english']['name'] = clean_text(cleaned_names['english']['name'], remove_common_words=False)
                
                # Get nutrition data for this variation
                nutrition_info = nutrition_dict.get(str(item['_id']), {})
                
                variation = {
                    'original_id': str(item['_id']),
                    'original_name': cleaned_original_name,
                    'names': cleaned_names,
                    'nutrition': {
                        'nutrition_id': str(nutrition_info.get('_id')) if nutrition_info.get('_id') else None,                        
                        'proteins_per_100g': nutrition_info.get('proteins_per_100g'),
                        'carbohydrates_per_100g': nutrition_info.get('carbohydrates_per_100g'),
                        'fats_per_100g': nutrition_info.get('fats_per_100g'),
                        'calories_per_100g': nutrition_info.get('calories_per_100g')
                    }
                }
                group_doc['variations'].append(variation)
            
            normalized_docs.append(group_doc)
        
        # Drop existing collection if it exists
        normalized_ingredients_collection.drop()
        
        # Insert new documents in batches
        batch_size = 1000
        for i in range(0, len(normalized_docs), batch_size):
            batch = normalized_docs[i:i + batch_size]
            normalized_ingredients_collection.insert_many(batch)
        
        print(f"Created {len(normalized_docs)} normalized ingredient groups")
        
        return normalized_docs
        
    except Exception as e:
        print(f"Error creating normalized collection: {str(e)}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    create_normalized_collection() 