#!/usr/bin/env python3
"""
Configuración para SteamRip Scraper
"""

import os
import json
from datetime import datetime


class Config:
    """Clase de configuración centralizada"""
    
    def __init__(self):
        # URLs y endpoints
        self.BASE_URL = os.getenv('STEAMRIP_BASE_URL', 'https://steamrip.com/games-list-page/')
        
        # Configuración de requests
        self.REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '2.0'))  # segundos entre requests
        self.REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))  # timeout en segundos
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
        
        # User Agent
        self.USER_AGENT = os.getenv('USER_AGENT', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Configuración de archivos
        self.OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')
        self.OUTPUT_FILENAME = os.getenv('OUTPUT_FILENAME', 'steamrip_games_{timestamp}.json')
        self.LOG_FILE = os.getenv('LOG_FILE', 'scraper.log')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        
        # Configuración de scraping
        self.MAX_GAMES = int(os.getenv('MAX_GAMES', '0'))  # 0 = sin límite
        self.INCLUDE_SCREENSHOTS = os.getenv('INCLUDE_SCREENSHOTS', 'true').lower() == 'true'
        self.INCLUDE_YOUTUBE = os.getenv('INCLUDE_YOUTUBE', 'true').lower() == 'true'
        
        # YouTube API (opcional)
        self.YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
        
        # Configuración de GitHub Actions
        self.GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
        self.GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY', '')
        
        # Crear directorio de salida si no existe
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
    
    def load_from_file(self, config_file):
        """Cargar configuración desde archivo JSON"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(self, key.upper()):
                    setattr(self, key.upper(), value)
                    
        except Exception as e:
            print(f"Error cargando configuración: {e}")
    
    def get_output_filename(self):
        """Generar nombre de archivo de salida"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.OUTPUT_FILENAME.format(timestamp=timestamp)
        return os.path.join(self.OUTPUT_DIR, filename)
    
    def to_dict(self):
        """Convertir configuración a diccionario"""
        return {
            key: value for key, value in self.__dict__.items() 
            if not key.startswith('_') and key not in ['GITHUB_TOKEN', 'YOUTUBE_API_KEY']
        }
    
    def __str__(self):
        """Representación string de la configuración"""
        config_dict = self.to_dict()
        return f"Config({', '.join([f'{k}={v}' for k, v in config_dict.items()])})"


if __name__ == '__main__':
    # Test de configuración
    config = Config()
    print("Configuración actual:")
    print(json.dumps(config.to_dict(), indent=2))
