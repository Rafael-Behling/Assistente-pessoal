import re
import html as htmllib

import httpx

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Sexta-Feira/1.0'}


def wikipedia_summary(query, timeout=6):
    try:
        r = httpx.get(
            'https://pt.wikipedia.org/w/api.php',
            params={'action': 'opensearch', 'search': query, 'limit': 1, 'format': 'json'},
            timeout=timeout, headers=UA,
        )
        titles = r.json()[1]
        if not titles:
            return ''
        title = titles[0].replace(' ', '_')
        r2 = httpx.get(
            f'https://pt.wikipedia.org/api/rest_v1/page/summary/{title}',
            timeout=timeout, headers=UA,
        )
        return r2.json().get('extract', '')
    except Exception:
        return ''


def ddg_search(query, limit=4, timeout=6):
    try:
        r = httpx.get('https://lite.duckduckgo.com/lite/', params={'q': query}, timeout=timeout, headers=UA)
        text = r.text
        results = []
        for m in re.finditer(r'<a[^>]*class="result-link"[^>]*>(.*?)</a>', text, re.S):
            title = htmllib.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            if title:
                results.append(title)
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


KNOWLEDGE_RE = re.compile(
    r'\b(?:quem (?:e|foi|sao)|o que (?:e|sao)|o que e|qual (?:e )?(?:a|o) (?:capital|populacao|idade)|'
    r'quando (?:surgiu|nasceu|foi|aconteceu)|onde fica|quantos (?:anos|habitantes|paises)|'
    r'noticias de|preco do|cotacao do)\b'
)


def looks_like_knowledge_question(q):
    return bool(KNOWLEDGE_RE.search(q))


def search_context(query, chars=700):
    wiki = wikipedia_summary(query)
    if wiki:
        return wiki[:chars]
    results = ddg_search(query)
    if results:
        return 'Resultados da busca: ' + ' | '.join(results)
    return ''
