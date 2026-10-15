from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    farmer_name = db.Column(db.String(100), nullable=False)
    mobile_number = db.Column(db.String(15), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    village = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    farm_name = db.Column(db.String(100), nullable=True)
    farm_size = db.Column(db.Float, nullable=True)
    primary_crop = db.Column(db.String(100), nullable=True)
    
    # Relational tables instead of JSON blobs
    crop_recommendations = db.relationship('CropRecommendation', backref='farmer', lazy=True, cascade="all, delete-orphan")
    soil_health_records = db.relationship('SoilHealthRecord', backref='farmer', lazy=True, cascade="all, delete-orphan")
    yield_predictions = db.relationship('YieldPrediction', backref='farmer', lazy=True, cascade="all, delete-orphan")
    irrigation_plans = db.relationship('IrrigationPlan', backref='farmer', lazy=True, cascade="all, delete-orphan")
    field_metrics = db.relationship('FieldSoilMetric', backref='farmer', lazy=True, cascade="all, delete-orphan")


class CropRecommendation(db.Model):
    __tablename__ = 'crop_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Input features
    nitrogen = db.Column(db.Float, nullable=True)
    phosphorus = db.Column(db.Float, nullable=True)
    potassium = db.Column(db.Float, nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    humidity = db.Column(db.Float, nullable=True)
    ph = db.Column(db.Float, nullable=True)
    rainfall = db.Column(db.Float, nullable=True)
    season = db.Column(db.String(50), nullable=True)
    soil_type = db.Column(db.String(50), nullable=True)
    
    # Model predictions / Output
    recommended_crop = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.String(20), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    sowing_time = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'type': 'Crop Recommendation',
            'date': self.created_at.isoformat() if self.created_at else '',
            'created_at': self.created_at,
            'input': {
                'nitrogen': self.nitrogen,
                'phosphorus': self.phosphorus,
                'potassium': self.potassium,
                'temperature': f"{self.temperature}°C" if self.temperature is not None else None,
                'humidity': f"{self.humidity}%" if self.humidity is not None else None,
                'ph': self.ph,
                'rainfall': f"{self.rainfall} mm" if self.rainfall is not None else None,
                'season': self.season,
                'soil_type': self.soil_type
            },
            'output': {
                'recommended_crop': self.recommended_crop,
                'confidence': self.confidence,
                'sowing_time': self.sowing_time,
                'reason': self.reason
            }
        }


class SoilHealthRecord(db.Model):
    __tablename__ = 'soil_health_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    ph = db.Column(db.Float, nullable=False)
    nitrogen = db.Column(db.Float, nullable=True)
    phosphorus = db.Column(db.Float, nullable=True)
    potassium = db.Column(db.Float, nullable=True)
    organic_carbon = db.Column(db.Float, nullable=True)
    
    status = db.Column(db.String(100), nullable=False)
    fertilizer_recommendation = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        inputs = {'ph': self.ph}
        if self.nitrogen is not None: inputs['nitrogen'] = self.nitrogen
        if self.phosphorus is not None: inputs['phosphorus'] = self.phosphorus
        if self.potassium is not None: inputs['potassium'] = self.potassium
        if self.organic_carbon is not None: inputs['organic_carbon'] = self.organic_carbon
        
        return {
            'type': 'Soil Health',
            'date': self.created_at.isoformat() if self.created_at else '',
            'created_at': self.created_at,
            'input': inputs,
            'output': {
                'status': self.status,
                'fertilizer_recommendation': self.fertilizer_recommendation
            }
        }


class YieldPrediction(db.Model):
    __tablename__ = 'yield_predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    crop = db.Column(db.String(100), nullable=False)
    farm_size = db.Column(db.Float, nullable=False)
    season = db.Column(db.String(50), nullable=True)
    
    total_yield = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.String(50), nullable=True)
    quality_grade = db.Column(db.String(50), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'type': 'Yield Prediction',
            'date': self.created_at.isoformat() if self.created_at else '',
            'created_at': self.created_at,
            'input': {
                'crop': self.crop,
                'farm_size': f"{self.farm_size} Acres",
                'season': self.season
            },
            'output': {
                'total_yield': f"{self.total_yield} Quintals",
                'profit': f"₹{int(self.profit):,}",
                'duration': self.duration_days,
                'quality': self.quality_grade
            }
        }


class IrrigationPlan(db.Model):
    __tablename__ = 'irrigation_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    farm_size = db.Column(db.Float, nullable=True)
    soil_type = db.Column(db.String(100), nullable=True)
    water_source = db.Column(db.String(100), nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    rain_chance = db.Column(db.Float, nullable=True)
    wind_speed = db.Column(db.Float, nullable=True)
    
    frequency = db.Column(db.String(100), nullable=False)
    warning = db.Column(db.Text, nullable=False)
    water_need = db.Column(db.String(50), default='Moderate')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        inputs = {}
        if self.soil_type: inputs['soil_type'] = self.soil_type
        if self.water_source: inputs['water_source'] = self.water_source
        if self.farm_size is not None: inputs['farm_size'] = f"{self.farm_size} Acres"
        if self.temperature is not None: inputs['temperature'] = f"{self.temperature}°C"
        if self.rain_chance is not None: inputs['rain_chance'] = f"{self.rain_chance}%"
        if self.wind_speed is not None: inputs['wind_speed'] = f"{self.wind_speed} km/h"
        
        return {
            'type': 'Irrigation Plan',
            'date': self.created_at.isoformat() if self.created_at else '',
            'created_at': self.created_at,
            'input': inputs,
            'output': {
                'frequency': self.frequency,
                'warning': self.warning,
                'water_need': self.water_need
            }
        }


class FieldSoilMetric(db.Model):
    __tablename__ = 'field_soil_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    farm_size = db.Column(db.Float, nullable=False)
    soil_type = db.Column(db.String(100), nullable=False)
    water_source = db.Column(db.String(100), nullable=False)
    
    recommended_crop = db.Column(db.String(100), nullable=False)
    seed_bags = db.Column(db.Integer, nullable=False)
    water_need = db.Column(db.String(50), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'type': 'Field & Soil Metrics',
            'date': self.created_at.isoformat() if self.created_at else '',
            'created_at': self.created_at,
            'input': {
                'farm_size': f"{self.farm_size} Acres",
                'soil': self.soil_type,
                'water': self.water_source
            },
            'output': {
                'recommended_crop': self.recommended_crop,
                'seed_bags': self.seed_bags,
                'water_need': self.water_need
            }
        }
