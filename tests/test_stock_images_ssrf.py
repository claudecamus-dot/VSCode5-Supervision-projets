"""Garde SSRF de `stock_images.fetch_to` (finding arbitré le 2026-09-02) :
la garde posée le 2026-09-01 ne filtre que le SCHÉMA (http/https) et laisse
passer une URL http vers une adresse interne. `img_url` vient d'Openverse, un
AGRÉGATEUR de sources tierces (Wikimedia, Flickr, StockSnap) — une donnée non
contrôlée — donc une URL `http://127.0.0.1/...`, `http://169.254.169.254/...`
(métadonnées cloud) ou un nom d'hôte qui RÉSOUT vers une telle adresse doit
être refusée avant tout téléchargement.

On exerce le VRAI `fetch_to` (pas un monkeypatch de la garde) : seuls les deux
bords réseau — la recherche Openverse (`search_photo`) et la résolution DNS
(`socket.getaddrinfo`) — sont substitués, comme le permet la consigne. Le point
d'ouverture réseau utilisé par `fetch_to` pour le téléchargement est
`_OUVREUR_TELECHARGEMENT.open(...)` (un opener urllib dédié, pas la fonction
`urllib.request.urlopen` brute) : soit rendu invoquant une AssertionError (pour
prouver que le téléchargement n'a JAMAIS lieu quand la garde refuse), soit
simulé pour le cas nominal (URL publique) afin de prouver qu'elle ne casse pas
le téléchargement légitime.

Deuxième volet (finding arbitré le 2026-09-02, suite) : une garde qui ne
valide que l'URL DE DÉPART ne protège rien contre une REDIRECTION HTTP —
`urlopen` suit les 3xx tout seul, sans repasser par la garde. Openverse agrège
des serveurs tiers (Wikimedia, Flickr, StockSnap...) : un serveur qui répond
`302 Location: http://127.0.0.1:8765/...` ferait viser une adresse interne
alors que seule l'URL initiale a été contrôlée — la garde mesurerait une
adresse et le programme en visiterait une autre. Les tests `test_redirect_*`
exercent directement `_RedirectValidant.redirect_request` (la VRAIE méthode
qu'urllib invoque à chaque saut) ; les tests `test_fetch_to_redirection_*`
déroulent la VRAIE mécanique d'ouverture d'urllib bout en bout (opener réel,
gestion d'erreurs réelle, notre handler réel) en ne remplaçant que le socket
`http.client.HTTPConnection` — jamais la garde elle-même.
"""
import email.message
import http.client
import importlib.util
import os
import socket

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(
    HUB, ".claude", "skills", "pptx-framed-image", "scripts", "stock_images.py")
spec = importlib.util.spec_from_file_location("stock_images_ssrf_cible", MODULE_PATH)
stock_images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stock_images)


def _urlopen_interdit(*args, **kwargs):
    raise AssertionError(
        "la garde SSRF a laissé passer l'URL : le téléchargement a été tenté")


def _mock_search(monkeypatch, url):
    """`search_photo` est l'appel réseau vers Openverse ; on le remplace pour
    injecter une `img_url` de test, exactement comme le ferait un résultat
    d'agrégateur malveillant ou compromis — sans appeler le vrai réseau."""
    monkeypatch.setattr(
        stock_images, "search_photo",
        lambda query, seed=0, aspect_ratio=None: (url, "un créateur", "https://example.org/page"))


def _mock_dns(monkeypatch, mapping):
    """Simule `socket.getaddrinfo` : `mapping` associe un nom d'hôte à une liste
    d'adresses IP littérales qu'il « résout »."""
    def _faux_getaddrinfo(host, *args, **kwargs):
        try:
            adresses = mapping[host]
        except KeyError:
            raise socket.gaierror(-2, f"Name or service not known (test): {host!r}")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in adresses]
    monkeypatch.setattr(socket, "getaddrinfo", _faux_getaddrinfo)


def _dns_interdit(monkeypatch):
    """Pour les cas IP littérale : la garde ne doit PAS avoir besoin d'une
    résolution DNS. On le prouve en faisant échouer tout appel."""
    def _boom(host, *args, **kwargs):
        raise AssertionError(f"DNS appelé alors que {host!r} est déjà une IP littérale")
    monkeypatch.setattr(socket, "getaddrinfo", _boom)


# ---------------------------------------------------------------------------
# IP littérale dans l'URL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8765/photo.jpg",
    "http://10.0.0.1/photo.jpg",
    "http://169.254.169.254/latest/meta-data/",
    "http://192.168.1.1/photo.jpg",
    "http://0.0.0.0/photo.jpg",
    "http://240.0.0.1/photo.jpg",
    "http://224.0.0.1/photo.jpg",
])
def test_ip_litterale_interne_refusee(monkeypatch, tmp_path, url):
    _mock_search(monkeypatch, url)
    _dns_interdit(monkeypatch)
    monkeypatch.setattr(stock_images._OUVREUR_TELECHARGEMENT, "open", _urlopen_interdit)
    with pytest.raises(ValueError):
        stock_images.fetch_to(str(tmp_path / "img.jpg"), "chat")


# ---------------------------------------------------------------------------
# IPv6 : bouclage, link-local, unique-local, IPv4 mappée
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://[::1]:8080/photo.jpg",
    "http://[fe80::1]/photo.jpg",
    "http://[fc00::1]/photo.jpg",
    "http://[::ffff:127.0.0.1]/photo.jpg",
])
def test_ipv6_interne_refusee(monkeypatch, tmp_path, url):
    _mock_search(monkeypatch, url)
    _dns_interdit(monkeypatch)
    monkeypatch.setattr(stock_images._OUVREUR_TELECHARGEMENT, "open", _urlopen_interdit)
    with pytest.raises(ValueError):
        stock_images.fetch_to(str(tmp_path / "img.jpg"), "chat")


# ---------------------------------------------------------------------------
# Nom d'hôte qui RÉSOUT vers une adresse interne — le cas le plus important :
# la garde doit résoudre, pas seulement parser la chaîne de l'URL.
# ---------------------------------------------------------------------------

def test_hostname_qui_resout_en_interne_refuse(monkeypatch, tmp_path):
    url = "http://images.cdn-tiers.example/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {"images.cdn-tiers.example": ["127.0.0.1"]})
    monkeypatch.setattr(stock_images._OUVREUR_TELECHARGEMENT, "open", _urlopen_interdit)
    with pytest.raises(ValueError):
        stock_images.fetch_to(str(tmp_path / "img.jpg"), "chat")


def test_hostname_multi_adresses_une_seule_interne_refuse(monkeypatch, tmp_path):
    """Un hôte qui résout vers PLUSIEURS adresses doit être refusé si l'UNE
    d'elles est interne — même si une autre est parfaitement publique."""
    url = "http://cdn-partage.example/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {"cdn-partage.example": ["93.184.216.34", "10.0.0.5"]})
    monkeypatch.setattr(stock_images._OUVREUR_TELECHARGEMENT, "open", _urlopen_interdit)
    with pytest.raises(ValueError):
        stock_images.fetch_to(str(tmp_path / "img.jpg"), "chat")


# ---------------------------------------------------------------------------
# Fail-closed : un hôte qui ne résout PAS DU TOUT doit être refusé, pas
# laissé passer.
# ---------------------------------------------------------------------------

def test_hostname_non_resolvable_refuse_fail_closed(monkeypatch, tmp_path):
    url = "http://ce-nom-nexiste-pas.invalid/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {})  # toute résolution lève socket.gaierror
    monkeypatch.setattr(stock_images._OUVREUR_TELECHARGEMENT, "open", _urlopen_interdit)
    with pytest.raises(ValueError):
        stock_images.fetch_to(str(tmp_path / "img.jpg"), "chat")


# ---------------------------------------------------------------------------
# Cas nominal : une URL https publique doit continuer de fonctionner — la
# garde ne doit pas casser le chemin légitime.
# ---------------------------------------------------------------------------

class _FausseReponseHTTP:
    def __init__(self, data):
        self._data = data
        self._pos = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, n=-1):
        if n is None or n < 0:
            chunk = self._data[self._pos:]
        else:
            chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def test_url_publique_ip_litterale_telecharge(monkeypatch, tmp_path):
    """IP publique littérale : ni interne, ni besoin de DNS."""
    url = "http://93.184.216.34/photo.jpg"
    _mock_search(monkeypatch, url)
    _dns_interdit(monkeypatch)
    contenu = b"donnees-image-factices"
    monkeypatch.setattr(
        stock_images._OUVREUR_TELECHARGEMENT, "open", lambda *a, **k: _FausseReponseHTTP(contenu))
    cible = tmp_path / "img.jpg"
    resultat = stock_images.fetch_to(str(cible), "chat")
    assert resultat == str(cible)
    assert cible.read_bytes() == contenu


def test_url_publique_hostname_resolu_telecharge(monkeypatch, tmp_path):
    """Nom d'hôte public qui résout vers une IP publique : la garde laisse
    passer, le téléchargement doit toujours réussir."""
    url = "https://images.example.com/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {"images.example.com": ["93.184.216.34"]})
    contenu = b"donnees-image-factices-2"
    monkeypatch.setattr(
        stock_images._OUVREUR_TELECHARGEMENT, "open", lambda *a, **k: _FausseReponseHTTP(contenu))
    cible = tmp_path / "img2.jpg"
    resultat = stock_images.fetch_to(str(cible), "montagne")
    assert resultat == str(cible)
    assert cible.read_bytes() == contenu


# ---------------------------------------------------------------------------
# Redirections HTTP — deuxième volet du finding SSRF (2026-09-02) : la garde
# de départ ne protège pas contre un serveur qui redirige APRÈS coup vers une
# adresse interne. `_RedirectValidant.redirect_request` doit re-valider CHAQUE
# cible avant de la suivre.
#
# Couche 1 : appel direct de la VRAIE méthode qu'urllib invoque à chaque saut
# (même signature, mêmes objets que ceux qu'urllib construirait) — rapide,
# isolé, sans dérouler tout l'opener.
# ---------------------------------------------------------------------------

def _fausse_requete(url):
    return stock_images.urllib.request.Request(url, headers={"User-Agent": "test/1.0"})


def test_redirect_request_vers_ip_litterale_interne_refuse(monkeypatch):
    _dns_interdit(monkeypatch)
    handler = stock_images._RedirectValidant()
    req = _fausse_requete("http://cdn-public.example/photo.jpg")
    with pytest.raises(ValueError, match="(?i)redirect"):
        handler.redirect_request(
            req, fp=None, code=302, msg="Found", headers={},
            newurl="http://127.0.0.1:8765/secret")


def test_redirect_request_vers_hostname_qui_resout_interne_refuse(monkeypatch):
    _mock_dns(monkeypatch, {"evil-cdn.example": ["10.0.0.5"]})
    handler = stock_images._RedirectValidant()
    req = _fausse_requete("http://cdn-public.example/photo.jpg")
    with pytest.raises(ValueError, match="(?i)redirect"):
        handler.redirect_request(
            req, fp=None, code=302, msg="Found", headers={},
            newurl="http://evil-cdn.example/secret")


def test_redirect_request_chaine_de_cibles_publiques_ok(monkeypatch):
    """Une chaîne de redirections légitimes (plusieurs sauts publics
    successifs) ne doit jamais être bloquée : chaque saut est validé
    indépendamment et passe tant qu'il reste public."""
    _mock_dns(monkeypatch, {
        "cdn-public-2.example": ["93.184.216.35"],
        "cdn-public-3.example": ["93.184.216.36"],
    })
    handler = stock_images._RedirectValidant()
    req = _fausse_requete("http://cdn-public.example/photo.jpg")

    premier_saut = handler.redirect_request(
        req, fp=None, code=302, msg="Found", headers={},
        newurl="http://cdn-public-2.example/photo2.jpg")
    assert premier_saut.full_url == "http://cdn-public-2.example/photo2.jpg"

    deuxieme_saut = handler.redirect_request(
        premier_saut, fp=None, code=302, msg="Found", headers={},
        newurl="http://cdn-public-3.example/photo3.jpg")
    assert deuxieme_saut.full_url == "http://cdn-public-3.example/photo3.jpg"


def test_redirect_request_ne_supprime_pas_la_limite_de_sauts():
    """La consigne est explicite : ne pas retirer la limite de sauts par
    défaut d'urllib (protection contre une boucle de redirection infinie) en
    ajoutant la validation d'hôte. `_RedirectValidant` doit donc rester une
    sous-classe qui HÉRITE de ces attributs, pas les redéfinir."""
    assert issubclass(stock_images._RedirectValidant, __import__("urllib.request", fromlist=["HTTPRedirectHandler"]).HTTPRedirectHandler)
    assert "max_redirections" not in stock_images._RedirectValidant.__dict__
    assert stock_images._RedirectValidant.max_redirections == \
        stock_images.urllib.request.HTTPRedirectHandler.max_redirections


# ---------------------------------------------------------------------------
# Couche 2 : `fetch_to` bout en bout, à travers la VRAIE mécanique d'urllib
# (opener réel, chaîne de gestion des erreurs réelle, notre handler réel) —
# seul le socket (`http.client.HTTPConnection`) est remplacé, jamais la garde.
# ---------------------------------------------------------------------------

class _FausseReponseHTTPBrute:
    """Une réponse HTTP brute (statut, en-têtes, corps), comme
    `http.client.HTTPConnection.getresponse()` la renverrait."""

    def __init__(self, status, reason, headers=None, corps=b""):
        self.status = self.code = status
        self.reason = self.msg = reason
        self.headers = email.message.Message()
        for cle, valeur in (headers or {}).items():
            self.headers[cle] = valeur
        self._corps = corps
        self._pos = 0

    def info(self):
        return self.headers

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, n=-1):
        if n is None or n < 0:
            morceau = self._corps[self._pos:]
        else:
            morceau = self._corps[self._pos:self._pos + n]
        self._pos += len(morceau)
        return morceau

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


class _FausseConnexionHTTP:
    """Remplace `http.client.HTTPConnection` : aucun socket réel n'est ouvert.
    Chaque instance consomme, dans l'ordre, la file de réponses préparée par
    le test — une entrée par saut de redirection, la dernière étant la
    réponse finale."""
    file_reponses = []
    debuglevel = 0  # lu comme attribut de CLASSE par HTTPHandler.__init__

    def __init__(self, host, timeout=None, **kwargs):
        self.host = host
        self.sock = None

    def set_debuglevel(self, level):
        pass

    def request(self, method, selector, body=None, headers=None, encode_chunked=False):
        pass  # rien à envoyer : il n'y a pas de socket derrière

    def getresponse(self):
        return _FausseConnexionHTTP.file_reponses.pop(0)

    def close(self):
        pass


def _preparer_chaine_http(monkeypatch, reponses):
    _FausseConnexionHTTP.file_reponses = list(reponses)
    monkeypatch.setattr(http.client, "HTTPConnection", _FausseConnexionHTTP)


def test_fetch_to_redirection_vers_ip_interne_refusee_bout_en_bout(monkeypatch, tmp_path):
    """Le serveur Openverse répond correctement à la validation initiale, PUIS
    redirige vers une adresse interne : la garde doit intercepter le saut, pas
    seulement l'URL de départ."""
    url = "http://cdn-public.example/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {"cdn-public.example": ["93.184.216.34"]})
    _preparer_chaine_http(monkeypatch, [
        _FausseReponseHTTPBrute(302, "Found", {"Location": "http://127.0.0.1:8765/secret"}),
    ])
    cible = tmp_path / "img.jpg"
    with pytest.raises(ValueError, match="(?i)redirect"):
        stock_images.fetch_to(str(cible), "chat")
    assert not cible.exists(), "aucun fichier ne doit être écrit quand la redirection est refusée"


def test_fetch_to_redirection_vers_hostname_interne_refusee_bout_en_bout(monkeypatch, tmp_path):
    url = "http://cdn-public.example/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {
        "cdn-public.example": ["93.184.216.34"],
        "images-cache.evil.example": ["169.254.169.254"],
    })
    _preparer_chaine_http(monkeypatch, [
        _FausseReponseHTTPBrute(
            302, "Found", {"Location": "http://images-cache.evil.example/secret"}),
    ])
    cible = tmp_path / "img.jpg"
    with pytest.raises(ValueError, match="(?i)redirect"):
        stock_images.fetch_to(str(cible), "chat")
    assert not cible.exists()


def test_fetch_to_chaine_redirections_publiques_fonctionne_bout_en_bout(monkeypatch, tmp_path):
    """Une chaîne de redirections légitimes (deux sauts publics puis le
    contenu) doit toujours aboutir — la garde ne casse pas le cas nominal."""
    url = "http://cdn-public.example/photo.jpg"
    _mock_search(monkeypatch, url)
    _mock_dns(monkeypatch, {
        "cdn-public.example": ["93.184.216.34"],
        "cdn-public-2.example": ["93.184.216.35"],
        "cdn-public-3.example": ["93.184.216.36"],
    })
    contenu = b"donnees-finales-apres-deux-sauts"
    _preparer_chaine_http(monkeypatch, [
        _FausseReponseHTTPBrute(
            302, "Found", {"Location": "http://cdn-public-2.example/photo2.jpg"}),
        _FausseReponseHTTPBrute(
            302, "Found", {"Location": "http://cdn-public-3.example/photo3.jpg"}),
        _FausseReponseHTTPBrute(200, "OK", {}, corps=contenu),
    ])
    cible = tmp_path / "img.jpg"
    resultat = stock_images.fetch_to(str(cible), "chat")
    assert resultat == str(cible)
    assert cible.read_bytes() == contenu


def test_opener_telechargement_contient_le_handler_de_redirection_valide():
    """Preuve structurelle que l'opener réellement utilisé par `fetch_to` pour
    le téléchargement porte bien NOTRE handler de redirection (et pas le
    `HTTPRedirectHandler` par défaut d'urllib qui ne valide rien)."""
    handlers_redirection = [
        h for h in stock_images._OUVREUR_TELECHARGEMENT.handlers
        if isinstance(h, stock_images.urllib.request.HTTPRedirectHandler)
    ]
    assert len(handlers_redirection) == 1
    assert isinstance(handlers_redirection[0], stock_images._RedirectValidant)
