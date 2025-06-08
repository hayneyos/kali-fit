import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Wizard Data Models
class WizardData(BaseModel):
    discovery_source: str = Field(..., description="Where user heard about the app")
    gender: str = Field(..., description="User's gender")
    weight: float = Field(..., description="User's weight in kg")
    height: float = Field(..., description="User's height in cm")
    birth_date: str = Field(..., description="User's birth date")
    main_goal: str = Field(..., description="User's main goal (lose/maintain/gain)")
    diet_type: str = Field(..., description="User's diet type")
    weight_goal: float = Field(..., description="User's target weight")
    workout_frequency: str = Field(..., description="Workouts per week")
    goal_pace: str = Field(..., description="Desired pace of progress")
    promo_code: Optional[str] = Field(None, description="Optional promo code")
    email: Optional[str] = Field(None, description="User's email")
    device_id: Optional[str] = Field(None, description="User's device ID")
    social: Optional[str] = Field(None, description="Social sharing preference")
    notifications_enabled: Optional[bool] = Field(False, description="Whether notifications are enabled")
    health_data_connected: Optional[bool] = Field(False, description="Whether health data is connected")


def calculate_age(birth_date: str) -> float:
    """Calculate age from birth date string"""
    try:
        birth = datetime.strptime(birth_date, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except Exception as e:
        raise ValueError(f"Invalid birth date format. Expected YYYY-MM-DD: {str(e)}")


def calculate_bmi(weight: float, height: float) -> float:
    """Calculate BMI from weight (kg) and height (m)"""
    try:
        height_m = height / 100  # Convert cm to m
        bmi = weight / (height_m * height_m)
        return round(bmi, 2)
    except Exception as e:
        raise ValueError(f"Error calculating BMI: {str(e)}")


def calculate_bmr(gender: str, weight: float, height: float, age: float) -> float:
    """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
    try:
        if gender.lower() == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:  # female
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        return round(bmr)
    except Exception as e:
        raise ValueError(f"Error calculating BMR: {str(e)}")


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """Calculate Total Daily Energy Expenditure based on activity level"""
    activity_multipliers = {
        "sedentary": 1.2,  # Little or no exercise
        "light": 1.375,  # Light exercise 1-3 days/week
        "moderate": 1.55,  # Moderate exercise 3-5 days/week
        "active": 1.725,  # Hard exercise 6-7 days/week
        "very_active": 1.9  # Very hard exercise & physical job or training twice per day
    }

    try:
        multiplier = activity_multipliers.get(activity_level.lower(), 1.2)
        return round(bmr * multiplier)
    except Exception as e:
        raise ValueError(f"Error calculating TDEE: {str(e)}")


def adjust_calories(tdee: float, weekly_goal: float) -> float:
    """Adjust calories based on weekly weight goal"""
    try:
        # Convert weekly goal from kg to calories
        # 1 kg of fat ≈ 7700 calories
        daily_adjustment = (weekly_goal * 7700) / 7
        return round(tdee + daily_adjustment)
    except Exception as e:
        raise ValueError(f"Error adjusting calories: {str(e)}")


def get_calorie_bounds(age: float, gender: str, activity_level: str) -> Tuple[float, float]:
    """Get recommended calorie bounds based on age, gender, and activity level"""
    try:
        # Base minimum calories
        min_calories = 1200 if gender.lower() == "female" else 1500

        # Adjust for age
        if age < 18:
            min_calories = max(min_calories, 1800)
        elif age > 50:
            min_calories = max(min_calories, 1300)

        # Adjust for activity level
        activity_multipliers = {
            "sedentary": 1.0,
            "light": 1.1,
            "moderate": 1.2,
            "active": 1.3,
            "very_active": 1.4
        }

        max_calories = min_calories * activity_multipliers.get(activity_level.lower(), 1.0) * 1.5

        return round(min_calories), round(max_calories)
    except Exception as e:
        raise ValueError(f"Error calculating calorie bounds: {str(e)}")


def calculate_macros(daily_calories: float) -> Tuple[float, float, float]:
    """Calculate macronutrient distribution"""
    try:
        # Protein: 30% of calories (4 calories per gram)
        protein_calories = daily_calories * 0.30
        protein_grams = round(protein_calories / 4)

        # Fats: 30% of calories (9 calories per gram)
        fat_calories = daily_calories * 0.30
        fat_grams = round(fat_calories / 9)

        # Carbs: 40% of calories (4 calories per gram)
        carb_calories = daily_calories * 0.40
        carb_grams = round(carb_calories / 4)

        return protein_grams, carb_grams, fat_grams
    except Exception as e:
        raise ValueError(f"Error calculating macros: {str(e)}")


def calculate_completion_date(current_weight: float, target_weight: float, weekly_goal: float) -> str:
    """Calculate estimated completion date based on weight goal and pace"""
    if weekly_goal == 0:
        return "N/A"  # No goal set

    weight_diff = abs(target_weight - current_weight)
    weeks_needed = weight_diff / abs(weekly_goal)

    completion_date = datetime.now() + timedelta(weeks=weeks_needed)
    return completion_date.strftime("%Y-%m-%d")
