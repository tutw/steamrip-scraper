#!/usr/bin/env python3
"""
SteamRip Games Scraper

Un scraper robusto y configurable para extraer información de juegos 
desde SteamRip.com con soporte para ejecución automática.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import hashlib
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re
from config import Config

class SteamRipScraper:
    def __init__(self, config=None):
        self.config = config or Config()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Configurar logging
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Estadísticas
        self.stats = {
            'games_processed': 0,
            'games_with_cover': 0,
            'games_with_screenshots': 0,
            'games_with_downloads': 0,
            'games_with_youtube': 0,
            'games_with_additional_info': 0,
            'errors': 0,
            'start_time': time.time()
        }

    def make_request(self, url, max_retries=3):
        """Hacer petición HTTP con reintentos y manejo de errores"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.config.REQUEST_TIMEOUT)
                response.raise_for_status()
                time.sleep(self.config.REQUEST_DELAY)
                return response
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error en intento {attempt + 1} para {url}: {e}")
                if attempt == max_retries - 1:
                    self.stats['errors'] += 1
                    raise
                time.sleep(2 ** attempt)  # Backoff exponencial

    def get_game_links(self):
        """Extraer enlaces de juegos desde la página principal"""
        self.logger.info(f"Extrayendo enlaces de juegos desde {self.config.BASE_URL}")
        
        response = self.make_request(self.config.BASE_URL)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscar enlaces de juegos
        game_links = []
        
        # Buscar todos los enlaces que apuntan a páginas de juegos
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href')
            if href and ('free-download' in href or 'download' in href):
                full_url = urljoin(self.config.BASE_URL, href)
                if full_url not in game_links:
                    game_links.append(full_url)
        
        self.logger.info(f"Encontrados {len(game_links)} enlaces de juegos")
        return game_links

    def extract_game_info(self, game_url):
        """Extraer información detallada de un juego"""
        try:
            self.logger.info(f"Procesando: {game_url}")
            
            response = self.make_request(game_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer información básica
            title = soup.find('h1') or soup.find('title')
            game_name = title.text.strip() if title else urlparse(game_url).path.split('/')[-2]
            
            # Limpiar nombre del juego
            game_name = re.sub(r'\s*free download.*$', '', game_name, flags=re.IGNORECASE)
            game_name = re.sub(r'\s*\(.*?\)\s*$', '', game_name).strip()
            
            # Generar ID único
            game_id = hashlib.md5(game_url.encode()).hexdigest()[:16]
            
            # Extraer descripción
            description_elem = soup.find('div', class_='entry-content') or soup.find('div', class_='content')
            description = description_elem.get_text(strip=True) if description_elem else ""
            
            # Extraer imagen de portada
            cover_image = ""
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src')
                if src and any(keyword in src.lower() for keyword in ['cover', 'poster', 'banner']):
                    cover_image = urljoin(game_url, src)
                    break
            
            if not cover_image and img_tags:
                # Tomar la primera imagen disponible
                cover_image = urljoin(game_url, img_tags[0].get('src', ''))
            
            # Extraer screenshots
            screenshots = []
            for img in img_tags:
                src = img.get('src', '')
                if src and any(keyword in src.lower() for keyword in ['screenshot', 'screen', 'shot']):
                    screenshots.append(urljoin(game_url, src))
            
            # Buscar enlaces de descarga
            download_links = self.extract_download_links(soup)
            
            # Generar enlace de YouTube
            youtube_search = f"https://www.youtube.com/results?search_query={game_name.replace(' ', '+')}+gameplay"
            
            # Extraer información adicional
            additional_info = self.extract_additional_info(soup)
            
            # Actualizar estadísticas
            self.stats['games_processed'] += 1
            if cover_image:
                self.stats['games_with_cover'] += 1
            if screenshots:
                self.stats['games_with_screenshots'] += 1
            if download_links:
                self.stats['games_with_downloads'] += 1
            if youtube_search:
                self.stats['games_with_youtube'] += 1
            if additional_info:
                self.stats['games_with_additional_info'] += 1
            
            game_data = {
                'id': game_id,
                'name': game_name,
                'description': description[:500] + '...' if len(description) > 500 else description,
                'cover_image': cover_image,
                'screenshots': screenshots,
                'youtube_gameplay': youtube_search,
                'download_links': download_links,
                'additional_info': additional_info,
                'scraped_url': game_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            self.logger.info(f"✅ Procesado exitosamente: {game_name}")
            return game_data
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando {game_url}: {e}")
            self.stats['errors'] += 1
            return None

    def extract_download_links(self, soup):
        """Extraer enlaces de descarga"""
        download_links = {}
        
        # Buscar enlaces con texto "DOWNLOAD HERE"
        download_buttons = soup.find_all(['a', 'button'], string=re.compile(r'DOWNLOAD\s+HERE', re.IGNORECASE))
        
        # También buscar por clases comunes
        download_buttons.extend(soup.find_all(['a', 'button'], class_=re.compile(r'download', re.IGNORECASE)))
        
        for button in download_buttons:
            href = button.get('href')
            if href:
                # Determinar plataforma por la URL
                platform = 'unknown'
                if 'megadb' in href.lower():
                    platform = 'megadb'
                elif 'buzzheavier' in href.lower() or 'buzzheave' in href.lower():
                    platform = 'buzzheavier'
                elif 'gofile' in href.lower():
                    platform = 'gofile'
                elif 'mega.nz' in href.lower():
                    platform = 'mega'
                elif 'mediafire' in href.lower():
                    platform = 'mediafire'
                elif 'rapidgator' in href.lower():
                    platform = 'rapidgator'
                
                download_links[platform] = href
        
        return download_links

    def extract_additional_info(self, soup):
        """Extraer información adicional del juego"""
        info = {}
        
        # Buscar información del sistema
        system_req = soup.find(string=re.compile(r'SYSTEM REQUIREMENTS', re.IGNORECASE))
        if system_req:
            req_section = system_req.find_parent()
            if req_section:
                info['system_requirements'] = req_section.get_text(strip=True)
        
        # Buscar información del juego
        game_info = soup.find(string=re.compile(r'GAME INFO', re.IGNORECASE))
        if game_info:
            info_section = game_info.find_parent()
            if info_section:
                text = info_section.get_text()
                
                # Extraer información específica
                genre_match = re.search(r'Genre:\s*([^\n]+)', text)
                if genre_match:
                    info['genre'] = genre_match.group(1).strip()
                
                developer_match = re.search(r'Developer:\s*([^\n]+)', text)
                if developer_match:
                    info['developer'] = developer_match.group(1).strip()
                
                size_match = re.search(r'Game Size:\s*([^\n]+)', text)
                if size_match:
                    info['size'] = size_match.group(1).strip()
                
                version_match = re.search(r'Version:\s*([^\n]+)', text)
                if version_match:
                    info['version'] = version_match.group(1).strip()
        
        return info

    def scrape_games(self, max_games=None):
        """Scraper principal"""
        self.logger.info(f"🚀 Iniciando scraper de SteamRip...")
        
        try:
            # Obtener enlaces de juegos
            game_links = self.get_game_links()
            
            if max_games:
                game_links = game_links[:max_games]
                self.logger.info(f"Limitando a {max_games} juegos para testing")
            
            games_data = []
            
            for i, game_url in enumerate(game_links, 1):
                self.logger.info(f"Progreso: {i}/{len(game_links)}")
                
                game_info = self.extract_game_info(game_url)
                if game_info:
                    games_data.append(game_info)
                
                # Pausa entre juegos
                if i < len(game_links):
                    time.sleep(self.config.REQUEST_DELAY)
            
            # Crear estructura JSON final
            result = {
                'timestamp': datetime.now().isoformat(),
                'total_games': len(games_data),
                'scraper_version': '1.0.0',
                'test_mode': bool(max_games),
                'statistics': self.get_statistics(),
                'games': games_data
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error crítico en el scraper: {e}")
            raise

    def get_statistics(self):
        """Obtener estadísticas del scraping"""
        elapsed_time = time.time() - self.stats['start_time']
        
        return {
            'games_processed': self.stats['games_processed'],
            'games_with_cover': self.stats['games_with_cover'],
            'games_with_screenshots': self.stats['games_with_screenshots'],
            'games_with_downloads': self.stats['games_with_downloads'],
            'games_with_youtube': self.stats['games_with_youtube'],
            'games_with_additional_info': self.stats['games_with_additional_info'],
            'errors': self.stats['errors'],
            'elapsed_time_seconds': round(elapsed_time, 2),
            'games_per_minute': round(self.stats['games_processed'] / (elapsed_time / 60), 2) if elapsed_time > 0 else 0
        }

    def save_to_file(self, data, filename=None):
        """Guardar datos en archivo JSON"""
        filename = filename or self.config.get_output_filename()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"✅ Datos guardados en: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"❌ Error guardando archivo: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description='SteamRip Games Scraper')
    parser.add_argument('--max-games', type=int, help='Máximo número de juegos a procesar (para testing)')
    parser.add_argument('--output', type=str, help='Archivo de salida personalizado')
    parser.add_argument('--config', type=str, help='Archivo de configuración JSON')
    parser.add_argument('--test', action='store_true', help='Ejecutar en modo de prueba (20 juegos)')
    
    args = parser.parse_args()
    
    # Cargar configuración
    config = Config()
    if args.config:
        config.load_from_file(args.config)
    
    # Crear scraper
    scraper = SteamRipScraper(config)
    
    # Determinar número de juegos
    max_games = args.max_games
    if args.test:
        max_games = 20
    
    try:
        # Ejecutar scraper
        print("🚀 Iniciando SteamRip Scraper...")
        print(f"📊 Configuración: {config}")
        
        data = scraper.scrape_games(max_games=max_games)
        
        # Guardar resultados
        filename = scraper.save_to_file(data, args.output)
        
        # Mostrar estadísticas
        stats = data['statistics']
        print("\n📊 ESTADÍSTICAS FINALES:")
        print(f"   Juegos procesados: {stats['games_processed']}")
        print(f"   Juegos con portada: {stats['games_with_cover']}")
        print(f"   Juegos con descargas: {stats['games_with_downloads']}")
        print(f"   Tiempo transcurrido: {stats['elapsed_time_seconds']}s")
        print(f"   Velocidad: {stats['games_per_minute']} juegos/min")
        print(f"   Errores: {stats['errors']}")
        print(f"\n✅ Scraping completado: {filename}")
        
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        exit(1)


if __name__ == '__main__':
    main()
