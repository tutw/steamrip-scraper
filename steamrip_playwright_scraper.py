#!/usr/bin/env python3

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import time
import hashlib
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re
import os

BASE_URL = "https://steamrip.com/games-list-page/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
OUTPUT_DIR = "output"

def get_game_links(page):
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)
    game_links = []
    for link in links:
        href = link.get('href')
        if href and re.search(r'-free-download', href):
            full_url = urljoin(BASE_URL, href)
            if full_url not in game_links:
                game_links.append(full_url)
    print(f"Encontrados {len(game_links)} enlaces de juegos")
    return game_links

def extract_game_info(page, game_url):
    page.goto(game_url)
    time.sleep(2)
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')

    title = soup.find('h1') or soup.find('title')
    game_name = title.text.strip() if title else urlparse(game_url).path.split('/')[-2]
    game_name = re.sub(r'\s*free download.*$', '', game_name, flags=re.IGNORECASE)
    game_name = re.sub(r'\s*\(.*?\)\s*$', '', game_name).strip()
    game_id = hashlib.md5(game_url.encode()).hexdigest()[:16]

    description_elem = soup.find('div', class_='entry-content') or soup.find('div', class_='content')
    description = description_elem.get_text(strip=True) if description_elem else ""

    cover_image = ""
    img_tags = soup.find_all('img')
    for img in img_tags:
        src = img.get('src')
        if src and any(keyword in src.lower() for keyword in ['cover', 'poster', 'banner']):
            cover_image = urljoin(game_url, src)
            break
    if not cover_image and img_tags:
        cover_image = urljoin(game_url, img_tags[0].get('src', ''))

    screenshots = []
    for img in img_tags:
        src = img.get('src', '')
        if src and any(keyword in src.lower() for keyword in ['screenshot', 'screen', 'shot']):
            screenshots.append(urljoin(game_url, src))

    download_links = {}
    youtube_search = f"https://www.youtube.com/results?search_query={game_name.replace(' ', '+')}+gameplay"
    additional_info = {}

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
    print(f"✅ Procesado: {game_name}")
    return game_data

def main():
    parser = argparse.ArgumentParser(description='SteamRip Games Scraper con Playwright')
    parser.add_argument('--max-games', type=int, help='Máximo número de juegos a procesar')
    parser.add_argument('--output', type=str, help='Archivo de salida')
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(BASE_URL)
        time.sleep(3)
        game_links = get_game_links(page)
        if args.max_games:
            game_links = game_links[:args.max_games]
        games_data = []
        for i, game_url in enumerate(game_links, 1):
            print(f"Progreso: {i}/{len(game_links)}")
            games_data.append(extract_game_info(page, game_url))
        browser.close()

    filename = args.output or f"{OUTPUT_DIR}/steamrip_games_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Scraping completado: {filename}")

if __name__ == "__main__":
    main()
