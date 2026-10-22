import os
import json
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

# 1. Konfiguration der News-Quellen (Beispiele für RSS & Scraping-Strukturen)
SOURCES = [
    {"name": "SPS-Magazin", "url": "https://sps-magazin.de/", "type": "scrape"},
    {"name": "Control Global", "url": "https://www.controlglobal.com/", "type": "scrape"},
    {"name": "Automation World", "url": "https://www.automationworld.com/", "type": "scrape"}
]

def get_latest_news():
    articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for source in SOURCES:
        try:
            response = requests.get(source["url"], headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"{source['name']}: HTTP {response.status_code}")
                continue
            print(f"{source['name']}: OK, {len(response.text)} Zeichen")
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Einfaches generisches Scraping von H2/H3-Überschriften und Links
            if source["name"] == "SPS-Magazin":
                for item in soup.find_all('h2')[:5]: # Die Top 5 Artikel
                    a_tag = item.find('a') if item.find('a') else item.parent.find('a')
                    if a_tag and a_tag.get('href'):
                        link = a_tag['href'] if a_tag['href'].startswith('http') else f"https://sps-magazin.de{a_tag['href']}"
                        articles.append({"title": item.get_text(strip=True), "link": link, "source": source["name"]})
            
            else: # Für Automation World & Control Global (Endeavor B2B Templates)
                for item in soup.find_all(['h2', 'h3'])[:5]:
                    a_tag = item.find('a')
                    if a_tag and a_tag.get('href'):
                        link = a_tag['href'] if a_tag['href'].startswith('http') else f"{source['url'].rstrip('/')}{a_tag['href']}"
                        articles.append({"title": item.get_text(strip=True), "link": link, "source": source["name"]})
                        
        except Exception as e:
            print(f"Fehler beim Laden von {source['name']}: {e}")
            
    return articles[:15] # Maximal 15 Artikel verarbeiten, um API-Kosten zu sparen

def summarize_with_ai(articles):
    # API-Key aus den GitHub Secrets laden
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Fehler: Kein ANTHROPIC_API_KEY gefunden!")
        return articles

    anthropic = Anthropic(api_key=api_key)
    
    # Bereite die Daten für Claude vor
    input_data = "\n".join([f"- [{a['source']}] {a['title']} (Link: {a['link']})" for a in articles])
    
    prompt = f"""
    Du bist ein Experte für industrielle Automatisierung (Industrial Automation, Industrie 4.0, SPS, Robotik).
    Hier ist eine Liste von aktuellen Schlagzeilen der Woche:
    {input_data}
    
    Bitte übersetze, filtere und fasse diese Schlagzeilen auf Deutsch zusammen. 
    Gib mir als Antwort AUSSCHLIESSLICH ein valides JSON-Array zurück (kein einleitender oder abschliessender Text, kein ```json).
    
    Das JSON-Format MUSS exakt so aussehen:
    [
      {{
        "title": "Deutsche Übersetzung/Anpassung des Titels",
        "original_title": "Originaler Titel",
        "source": "Name der Quelle",
        "link": "Originaler Link",
        "summary": "Eine prägnante Zusammenfassung (2-3 Sätze) auf Deutsch, warum das für die Automatisierungsbranche wichtig ist."
      }}
    ]
    """
    
    try:
        response = anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Antwort bereinigen und parsen
        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"Fehler bei der KI-Zusammenfassung: {e}")
        return articles

if __name__ == "__main__":
    print("Scrape aktuelle News...")
    raw_news = get_latest_news()

    if not raw_news:
        print("Keine News gefunden, Abbruch.")
        raise SystemExit(1)

    print(f"{len(raw_news)} Artikel gefunden. Starte KI-Zusammenfassung...")
    final_news = summarize_with_ai(raw_news)

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(final_news, f, ensure_ascii=False, indent=2)
    print("news.json erfolgreich aktualisiert!")
