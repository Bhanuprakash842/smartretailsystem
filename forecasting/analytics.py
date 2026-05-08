"""
analytics.py
============
Comprehensive analytics engine for demand forecasting with product, week, and day-wise insights.
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_historical_data():
    """Load and prepare historical demand data."""
    df = pd.read_csv(os.path.join(DATA_DIR, "daily_demand.csv"), parse_dates=["date"])
    return df

def get_product_analytics(product_id=None, days=30):
    """Get comprehensive product-wise analytics."""
    df = load_historical_data()
    
    if product_id:
        df = df[df['product_id'] == product_id]
    
    # Last N days analysis
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=days)
    recent_df = df[df['date'] >= start_date]
    
    analytics = {
        'total_revenue': recent_df['revenue'].sum(),
        'total_quantity': recent_df['qty_sold'].sum(),
        'avg_daily_demand': recent_df['qty_sold'].mean(),
        'peak_demand_day': recent_df.loc[recent_df['qty_sold'].idxmax(), 'date'].strftime('%Y-%m-%d'),
        'peak_demand_qty': recent_df['qty_sold'].max(),
        'lowest_demand_day': recent_df.loc[recent_df['qty_sold'].idxmin(), 'date'].strftime('%Y-%m-%d'),
        'lowest_demand_qty': recent_df['qty_sold'].min(),
        'demand_volatility': recent_df['qty_sold'].std(),
        'growth_rate': calculate_growth_rate(recent_df),
        'weekend_vs_weekday': calculate_weekend_weekday_ratio(recent_df),
        'promotion_impact': calculate_promotion_impact(recent_df)
    }
    
    if product_id:
        product_info = recent_df.iloc[0][['product_name', 'category', 'price']].to_dict()
        analytics.update(product_info)
    
    return analytics

def get_weekly_analytics(product_id=None, weeks=12):
    """Get week-wise demand analytics."""
    df = load_historical_data()
    
    if product_id:
        df = df[df['product_id'] == product_id]
    
    # Group by week
    df['week'] = df['date'].dt.isocalendar().week
    df['year'] = df['date'].dt.year
    weekly_data = df.groupby(['year', 'week']).agg({
        'qty_sold': ['sum', 'mean', 'std'],
        'revenue': 'sum',
        'date': 'min'
    }).reset_index()
    
    # Flatten column names
    weekly_data.columns = ['year', 'week', 'total_qty', 'avg_daily_qty', 'qty_std', 'total_revenue', 'week_start']
    
    # Sort and limit to recent weeks
    weekly_data = weekly_data.sort_values(['year', 'week']).tail(weeks)
    
    # Add trend analysis
    weekly_data['trend'] = calculate_trend(weekly_data['total_qty'])
    weekly_data['week_label'] = weekly_data.apply(lambda x: f"Week {x['week']} ({x['week_start'].strftime('%b %d')})", axis=1)
    
    return weekly_data.to_dict('records')

def get_daily_analytics(product_id=None, days=30):
    """Get day-wise detailed analytics."""
    df = load_historical_data()
    
    if product_id:
        df = df[df['product_id'] == product_id]
    
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=days)
    daily_df = df[df['date'] >= start_date].copy()
    
    # Add day-level metrics
    daily_df['demand_category'] = pd.cut(daily_df['qty_sold'], 
                                        bins=[0, 5, 10, 20, float('inf')],
                                        labels=['Low', 'Medium', 'High', 'Very High'])
    
    # Sort by date
    daily_df = daily_df.sort_values('date')
    
    return daily_df.to_dict('records')

def calculate_growth_rate(df):
    """Calculate demand growth rate."""
    if len(df) < 7:
        return 0
    
    first_week = df.head(7)['qty_sold'].mean()
    last_week = df.tail(7)['qty_sold'].mean()
    
    if first_week == 0:
        return 0
    
    return ((last_week - first_week) / first_week) * 100

def calculate_weekend_weekday_ratio(df):
    """Calculate weekend vs weekday demand ratio."""
    weekend_demand = df[df['is_weekend'] == 1]['qty_sold'].mean()
    weekday_demand = df[df['is_weekend'] == 0]['qty_sold'].mean()
    
    if weekday_demand == 0:
        return 1
    
    return weekend_demand / weekday_demand

def calculate_promotion_impact(df):
    """Calculate promotion impact on demand."""
    promo_demand = df[df['is_promotion'] == 1]['qty_sold'].mean()
    normal_demand = df[df['is_promotion'] == 0]['qty_sold'].mean()
    
    if normal_demand == 0:
        return 0
    
    return ((promo_demand - normal_demand) / normal_demand) * 100

def calculate_trend(series):
    """Calculate trend direction for a series."""
    if len(series) < 2:
        return 'stable'
    
    recent_avg = series.tail(3).mean()
    earlier_avg = series.head(max(3, len(series)//2)).mean()
    
    if recent_avg > earlier_avg * 1.1:
        return 'upward'
    elif recent_avg < earlier_avg * 0.9:
        return 'downward'
    else:
        return 'stable'

def get_category_performance():
    """Get performance analytics by category."""
    df = load_historical_data()
    
    category_stats = df.groupby('category').agg({
        'qty_sold': ['sum', 'mean', 'std'],
        'revenue': 'sum',
        'product_id': 'nunique'
    }).reset_index()
    
    category_stats.columns = ['category', 'total_qty', 'avg_qty', 'qty_std', 'total_revenue', 'product_count']
    category_stats['demand_stability'] = category_stats['qty_std'] / category_stats['avg_qty']
    
    return category_stats.to_dict('records')

def get_seasonal_patterns(product_id=None):
    """Analyze seasonal demand patterns."""
    df = load_historical_data()
    
    if product_id:
        df = df[df['product_id'] == product_id]
    
    seasonal_data = df.groupby('season').agg({
        'qty_sold': ['mean', 'sum', 'std'],
        'revenue': 'sum'
    }).reset_index()
    
    seasonal_data.columns = ['season', 'avg_demand', 'total_demand', 'demand_std', 'total_revenue']
    
    return seasonal_data.to_dict('records')

def get_top_performers(metric='revenue', limit=10):
    """Get top performing products by various metrics."""
    df = load_historical_data()
    
    if metric == 'revenue':
        performers = df.groupby(['product_id', 'product_name', 'category'])['revenue'].sum().reset_index()
        performers = performers.sort_values('revenue', ascending=False)
    elif metric == 'quantity':
        performers = df.groupby(['product_id', 'product_name', 'category'])['qty_sold'].sum().reset_index()
        performers = performers.sort_values('qty_sold', ascending=False)
    elif metric == 'consistency':
        performers = df.groupby(['product_id', 'product_name', 'category'])['qty_sold'].std().reset_index()
        performers = performers.sort_values('qty_sold', ascending=True)
    
    return performers.head(limit).to_dict('records')

def get_demand_forecast_summary(product_id, days=30):
    """Get forecast summary with confidence intervals."""
    from forecasting.predict import predict_range
    
    end_date = date.today() + timedelta(days=30)
    start_date = end_date - timedelta(days=days)
    
    forecasts = predict_range(product_id, start_date, end_date)
    
    summary = {
        'avg_predicted_demand': np.mean([f['predicted_qty'] for f in forecasts]),
        'max_predicted_demand': max([f['predicted_qty'] for f in forecasts]),
        'min_predicted_demand': min([f['predicted_qty'] for f in forecasts]),
        'total_predicted_revenue': sum([f['predicted_revenue'] for f in forecasts]),
        'avg_confidence_range': np.mean([f['confidence_high'] - f['confidence_low'] for f in forecasts]),
        'forecast_volatility': np.std([f['predicted_qty'] for f in forecasts])
    }
    
    return summary
