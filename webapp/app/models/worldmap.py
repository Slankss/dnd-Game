"""Harita — grubun nerede olduğu ve bugüne kadar keşfettiği yerler.

Oyun "neredeyiz?" sorusunu eskiden tek bir metin alanıyla (`location`)
cevaplıyordu; grup ikiye ayrıldığında ya da bir yer keşfedildiğinde bunun
kaydı hiçbir yerde durmuyordu. Harita üç şeyi birlikte tutar:

  * `current`  — grubun ana konumu (tek metin, `world_state.location` ile eşlenir)
  * `places`   — bilinen yerler: türü, durumu, tehlike seviyesi, komşuları
  * `party`    — kim nerede (grup dağıldığında karakter başına konum)

Anlatıcı bunu state-update'in `map` alanıyla günceller; sunucu ayrıca her
turda `location` ve `characters.<isim>.location` değerlerinden haritayı
kendiliğinden senkronlar — model unutsa bile harita akmaya devam eder.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .text import canonical_name, norm_tr

PLACE_FIELDS = ("kind", "category", "city", "x", "y", "known", "status",
                "danger", "notes", "links", "discovered_day", "visited")

# Bir yer hakkında NE KADAR bilindiği. Harita bunu görsel olarak da ayırır:
# duyulmuş bir yer haritada silik bir soru işaretidir, keşfedilmiş bir yer
# adıyla/türüyle/tehlikesiyle çizilir. Sunucu ayrıca oyuncuya giden gövdeden
# bilinmeyen yerin ayrıntılarını AYIKLAR (bkz. public_place) — "bilinmiyorsa
# haritada da görünmesin" kuralı veri katmanında uygulanır, sadece çizimde değil.
# `bilinmiyor` en alt düzeydir ve OYUNCUYA HİÇ GÖNDERİLMEZ: harita oyunun
# başında bütünüyle üretilir (şehirler, mekanlar, yollar, mesafeler), ama
# grubun henüz duymadığı yerler haritada yoktur. Böylece hem dünya tutarlı ve
# önceden hesaplanmış olur hem de keşif duygusu korunur.
KNOWLEDGE_LEVELS = ("bilinmiyor", "duyuldu", "görüldü", "keşfedildi")

KNOWLEDGE_RANK = {"bilinmiyor": 0, "duyuldu": 1, "görüldü": 2, "keşfedildi": 3}

KNOWLEDGE_ALIASES = {
    "duyuldu": "duyuldu", "duyuldu ": "duyuldu", "söylenti": "duyuldu",
    "soylenti": "duyuldu", "bahsedildi": "duyuldu", "bilinmiyor": "duyuldu",
    "duyum": "duyuldu", "rivayet": "duyuldu",
    "görüldü": "görüldü", "goruldu": "görüldü", "uzaktan": "görüldü",
    "uzaktan görüldü": "görüldü", "gözlendi": "görüldü", "gozlendi": "görüldü",
    "yaklaşıldı": "görüldü", "yaklasildi": "görüldü",
    "keşfedildi": "keşfedildi", "kesfedildi": "keşfedildi",
    "gezildi": "keşfedildi", "içeri girildi": "keşfedildi",
    "ziyaret edildi": "keşfedildi", "biliniyor": "keşfedildi",
}

# Tehlike seviyeleri (arayüzdeki rozet rengi buna bakar).
DANGER_LEVELS = ("güvenli", "temkinli", "tehlikeli", "ölümcül", "bilinmiyor")

DANGER_ALIASES = {
    "guvenli": "güvenli", "sakin": "güvenli", "temiz": "güvenli",
    "temkinli": "temkinli", "orta": "temkinli", "şüpheli": "temkinli",
    "supheli": "temkinli",
    "tehlikeli": "tehlikeli", "riskli": "tehlikeli", "yüksek": "tehlikeli",
    "yuksek": "tehlikeli",
    "ölümcül": "ölümcül", "olumcul": "ölümcül", "kritik": "ölümcül",
}


def canon_danger(value) -> str:
    if not isinstance(value, str) or not value.strip():
        return "bilinmiyor"
    raw = value.strip().lower()
    if raw in DANGER_LEVELS:
        return raw
    key = norm_tr(raw)
    for alias, canon in DANGER_ALIASES.items():
        if norm_tr(alias) == key:
            return canon
    return "bilinmiyor"


def canon_known(value) -> str:
    """Bilgi düzeyini kanonlaştırır; tanınmayan değer 'duyuldu'ya düşer."""
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip().lower()
    # "bilinmiyor" bilerek dışarıda: anlatıcı onu "pek bir şey bilmiyoruz"
    # anlamında yazıyor, takma ad tablosu onu "duyuldu"ya çeviriyor. Gerçek
    # gizlilik yalnız üretecin `Place.hide()` çağrısıyla kurulur.
    if raw in KNOWLEDGE_LEVELS and raw != "bilinmiyor":
        return raw
    key = norm_tr(raw)
    for alias, canon in KNOWLEDGE_ALIASES.items():
        if norm_tr(alias) == key:
            return canon
    return "duyuldu"


def canon_hidden(value) -> bool:
    """Yalnız üretecin yazdığı ham 'bilinmiyor' gizli sayılır.

    Anlatıcı 'bilinmiyor' yazdığında bunu 'pek bir şey bilmiyoruz' anlamında
    kullanıyor — o yeri haritadan silmek yanlış olurdu. Bu yüzden takma ad
    tablosu 'bilinmiyor'u 'duyuldu'ya çevirmeye devam eder; gerçek gizlilik
    yalnızca `Place.hide()` ile kurulur."""
    return str(value or "").strip() == "bilinmiyor"


def knowledge_of(place: dict) -> str:
    """Bir yer kaydının bilgi düzeyi.

    Anlatıcı `known` yazmadıysa mevcut alanlardan türetilir: gidilmiş bir yer
    keşfedilmiştir, türü/durumu/tehlikesi bilinen bir yer en azından
    görülmüştür, sadece adı geçen bir yer duyulmuştur. Böylece bu alan
    eklenmeden önce başlamış oyunlar da doğru çizilir."""
    place = place if isinstance(place, dict) else {}
    if canon_hidden(place.get("known")):
        return "bilinmiyor"
    known = canon_known(place.get("known"))
    if known:
        return known
    if place.get("visited"):
        return "keşfedildi"
    if place.get("kind") or place.get("status") or (
            place.get("danger") and place.get("danger") != "bilinmiyor"):
        return "görüldü"
    return "duyuldu"


def public_place(place: dict) -> dict:
    """Bir yer kaydının OYUNCUYA giden hali.

    Bilinmeyen yer haritada ayrıntılı görünmemeli — ve bu, sadece çizim
    kararı değil veri kararıdır: ayrıntılar buradan AYIKLANIR, tarayıcıya hiç
    gitmez. Aksi halde F12 açan bir oyuncu henüz keşfetmediği bir yerin
    tehlikesini ve notunu okuyabilirdi.

      bilinmiyor  → gövdeye HİÇ GİRMEZ (None döner). Harita oyunun başında
                    bütünüyle üretilir; grubun duymadığı yer haritada yoktur.
      duyuldu     → adı, bağlı olduğu şehir ve kabaca yeri (haritada silik bir
                    işaret); türü/durumu/tehlikesi/notu GÖNDERİLMEZ
      görüldü     → kategori, tür, durum, tehlike, komşuluk
      keşfedildi  → tam kayıt (not dahil)
    """
    place = place if isinstance(place, dict) else {}
    known = knowledge_of(place)
    if known == "bilinmiyor":
        return None
    body = {"known": known, "visited": bool(place.get("visited"))}
    # Konum ve şehir en alt düzeyde bile gider: "duydun" demek nerede olduğunu
    # kabaca biliyorsun demektir, yoksa haritaya çizilemez.
    for name in ("city", "x", "y"):
        if place.get(name) not in (None, ""):
            body[name] = place[name]
    if known == "duyuldu":
        return body
    for name in ("kind", "category", "status", "danger", "links", "discovered_day"):
        if place.get(name) not in (None, "", []):
            body[name] = place[name]
    if known == "keşfedildi" and place.get("notes"):
        body["notes"] = place["notes"]
    return body


def public_roads(roads, gorunur_yerler) -> list:
    """Oyuncuya giden yollar — iki ucu da BİLİNEN yollar.

    Bilinmeyen bir yere giden yol çizilirse yerin varlığı sızardı; bu yüzden
    süzgeç veri katmanında."""
    out = []
    for road in roads or []:
        if not isinstance(road, dict):
            continue
        if road.get("a") not in gorunur_yerler or road.get("b") not in gorunur_yerler:
            continue
        out.append({k: v for k, v in road.items() if k != "known"})
    return out


@dataclass
class Place(DictModel):
    """`world_state.map.places.<ad>`."""

    KNOWN = PLACE_FIELDS

    kind: object = None            # sığınak / kamp / harabe / yol / tesis …
    category: object = None        # katalog yer türü (karakol, hastane, market…)
    city: object = None            # hangi şehre/kasabaya bağlı
    x: object = None               # harita koordinatı (km)
    y: object = None
    known: object = None           # bilinmiyor | duyuldu | görüldü | keşfedildi
    status: object = None          # kısa durum: "barikatlı", "yanmış", "terk"
    danger: object = None
    notes: object = None
    links: list = field(default_factory=list)   # komşu yerler (yürüme mesafesi)
    discovered_day: object = None
    visited: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Place":
        data = data or {}
        place = cls()
        place.extra, place.key_order = cls._split(data)
        for name in ("kind", "category", "city", "x", "y", "known", "status",
                     "danger", "notes", "discovered_day", "visited"):
            setattr(place, name, data.get(name))
        if isinstance(data.get("links"), list):
            place.links = [str(x) for x in data["links"] if isinstance(x, str)]
        elif "links" in data:
            place.extra["links"] = data["links"]
        return place

    @classmethod
    def new(cls, day=None) -> "Place":
        # Yeni bir yer adı ilk kez geçtiğinde bilinen tek şey ADIDIR.
        place = cls(kind="", known="duyuldu", status="", danger="bilinmiyor",
                    notes="", links=[], discovered_day=day, visited=False)
        place.key_order = list(PLACE_FIELDS)
        return place

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in
                  ("kind", "category", "city", "x", "y", "known", "status",
                   "danger", "notes")}
        values["links"] = self.links
        values["discovered_day"] = self.discovered_day
        values["visited"] = self.visited
        return self._emit(values)

    @property
    def knowledge(self) -> str:
        return knowledge_of(self.to_dict())

    def raise_knowledge(self, level: str) -> None:
        """Bilgi düzeyini YÜKSELTİR, asla düşürmez: bir kez keşfedilen yer
        sonradan 'duyuldu'ya dönmez."""
        level = canon_known(level) or "duyuldu"
        if KNOWLEDGE_RANK.get(level, 1) > KNOWLEDGE_RANK.get(self.knowledge, 1):
            self._set("known", level)
            if level == "keşfedildi":
                self._set("visited", True)

    def hide(self) -> None:
        """Yeri OYUNCUDAN gizler: dünyada var ama grup henüz duymadı."""
        self._set("known", "bilinmiyor")

    @property
    def hidden(self) -> bool:
        return self.knowledge == "bilinmiyor"

    def merge_patch(self, fields: dict) -> None:
        # Anlatıcı bir yeri yamalıyorsa o yer artık en azından DUYULMUŞTUR:
        # sahnede adı geçen bir yer haritadan gizli kalamaz.
        if self.hidden:
            self._set("known", "duyuldu")
        for name in ("kind", "category", "city", "status", "notes"):
            value = fields.get(name)
            if isinstance(value, str):
                self._set(name, value)
        if "danger" in fields:
            self._set("danger", canon_danger(fields.get("danger")))
        if "known" in fields:
            self.raise_knowledge(fields.get("known"))
        for name in ("x", "y"):
            if isinstance(fields.get(name), (int, float)):
                self._set(name, float(fields[name]))
        if isinstance(fields.get("discovered_day"), (int, float)):
            self._set("discovered_day", int(fields["discovered_day"]))
        if isinstance(fields.get("visited"), bool):
            self._set("visited", fields["visited"])
        links = fields.get("links")
        if isinstance(links, str):
            links = [links]
        if isinstance(links, list):
            self._touch("links")
            for name in links:
                if isinstance(name, str) and name.strip() and name not in self.links:
                    self.links.append(name.strip())


@dataclass
class Road(DictModel):
    """İki mekan arasındaki BİR yol.

    İki yer arasında birden fazla yol olabilir (hızlı ama açık anayol ile
    yavaş ama gizli patika), tek yol olabilir (tek köprü) ya da hiç yol
    olmayabilir — o zaman dolambaçlı gitmek gerekir. Rota hesabı bunu
    kendiliğinden çözer (`WorldMap.route`).

    `km` yolun GERÇEK uzunluğudur; kuş uçuşu mesafeye yol türünün sapma
    katsayısı uygulanarak üretimde hesaplanır. `status` geçilebilirliği ve
    süreyi etkiler: çökük bir yol hiç kullanılamaz.
    """

    KNOWN = ("a", "b", "kind", "km", "status", "risk", "notes", "known")

    a: object = None
    b: object = None
    kind: object = None          # anayol | cadde | ara sokak | patika | köprü …
    km: object = None
    status: object = None        # açık | tıkalı | barikatlı | çökük
    risk: object = None          # 1-5, yol türünden gelir
    notes: object = None
    known: object = None         # oyuncu bu yolu biliyor mu (duyuldu/keşfedildi)
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Road":
        data = data or {}
        road = cls()
        road.extra, road.key_order = cls._split(data)
        for name in ("a", "b", "kind", "status", "notes", "known"):
            setattr(road, name, data.get(name))
        for name in ("km", "risk"):
            value = data.get(name)
            if isinstance(value, (int, float)):
                setattr(road, name, float(value) if name == "km" else int(value))
        return road

    @classmethod
    def new(cls, a, b, kind, km, status="açık", risk=2, notes="") -> "Road":
        road = cls(a=a, b=b, kind=kind, km=round(float(km), 2), status=status,
                   risk=int(risk), notes=notes, known="bilinmiyor")
        road.key_order = list(cls.KNOWN)
        return road

    def to_dict(self) -> dict:
        return self._emit({name: getattr(self, name) for name in self.KNOWN})

    @property
    def passable(self) -> bool:
        return str(self.status or "açık") != "çökük"

    def cost(self) -> float:
        """Rota hesabındaki ağırlık: uzunluk × durum çarpanı."""
        carpan = {"açık": 1.0, "tıkalı": 1.6, "barikatlı": 1.8}.get(
            str(self.status or "açık"), 1.0)
        return float(self.km or 0) * carpan

    def other(self, name: str):
        if name == self.a:
            return self.b
        if name == self.b:
            return self.a
        return None


@dataclass
class WorldMap(DictModel):
    """`world_state.map`."""

    KNOWN = ("current", "size", "cities", "places", "roads", "party")

    current: object = None
    size: object = None                          # küçük | orta | büyük
    cities: dict = field(default_factory=dict)   # {ad: {tur, not, x, y}}
    places: dict = field(default_factory=dict)
    roads: list = field(default_factory=list)
    party: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "WorldMap":
        data = data or {}
        world_map = cls()
        world_map.extra, world_map.key_order = cls._split(data)
        world_map.current = data.get("current")
        world_map.size = data.get("size")
        raw = data.get("cities")
        if isinstance(raw, dict):
            world_map.cities = {str(k): v for k, v in raw.items()
                                if isinstance(v, dict)}
        raw = data.get("roads")
        if isinstance(raw, list):
            world_map.roads = [Road.from_dict(x) for x in raw
                               if isinstance(x, dict)]
        raw = data.get("places")
        if isinstance(raw, dict):
            world_map.places = {name: Place.from_dict(value)
                                for name, value in raw.items()
                                if isinstance(value, dict)}
        raw = data.get("party")
        if isinstance(raw, dict):
            world_map.party = {str(k): str(v) for k, v in raw.items()
                               if isinstance(v, str)}
        return world_map

    @classmethod
    def new(cls) -> "WorldMap":
        world_map = cls(current=None, size=None, cities={}, places={},
                        roads=[], party={})
        world_map.key_order = ["current", "places", "party"]
        return world_map

    def to_dict(self) -> dict:
        return self._emit({
            "current": self.current,
            "size": self.size,
            "cities": dict(self.cities),
            "places": {name: place.to_dict() for name, place in self.places.items()},
            "roads": [road.to_dict() for road in self.roads],
            "party": dict(self.party),
        })

    # ------------------------------------------------------------ yardımcılar
    def ensure_place(self, name: str, day=None) -> Place:
        """Yer kaydı yoksa açar; adı büyük/küçük harf farkıyla tekrarlamaz."""
        key = canonical_name(self.places, name) or name
        place = self.places.get(key)
        if not isinstance(place, Place):
            place = self.places[key] = Place.new(day)
        return place

    def go(self, name: str, day=None) -> None:
        """Ana konumu değiştirir; gidilen yer artık KEŞFEDİLMİŞTİR."""
        if not isinstance(name, str) or not name.strip():
            return
        name = name.strip()
        previous = self.current
        self._set("current", name)
        place = self.ensure_place(name, day)
        place._set("visited", True)
        place.raise_knowledge("keşfedildi")
        if place.discovered_day is None and day is not None:
            place._set("discovered_day", day)
        # Yürüyerek gelinen yer komşudur: rota kendiliğinden çizilsin.
        if isinstance(previous, str) and previous.strip() and previous != name:
            self.link(previous, name)
            for road in self.roads_between(previous, name):
                road._set("known", "keşfedildi")
        # Bir yere varmak haritayı bir adım büyütür: yol ağzındaki tabelalar,
        # karşı tepedeki bina, komşu mahallenin adı artık DUYULMUŞTUR.
        self.reveal_neighbours(name)
        self._touch("places")

    def link(self, a: str, b: str) -> None:
        for src, dst in ((a, b), (b, a)):
            place = self.ensure_place(src)
            if dst not in place.links:
                place._touch("links")
                place.links.append(dst)

    def place_person(self, name: str, where: str, day=None) -> None:
        """Karakteri haritaya yerleştirir (grup dağıldığında kim nerede).

        Bir karakterin FİİLEN bulunduğu yer keşfedilmiş sayılır — orayı
        gözleriyle görüyor demektir."""
        if not isinstance(name, str) or not isinstance(where, str) or not where.strip():
            return
        self._touch("party")
        self.party[name] = where.strip()
        place = self.ensure_place(where.strip(), day)
        place.raise_knowledge("keşfedildi")
        if place.discovered_day is None and day is not None:
            place._set("discovered_day", day)

    def adjacency(self) -> dict:
        """{yer: [komşular]} — göç motorunun kullandığı komşuluk grafiği.

        Hem YOLLARDAN hem `links` alanından beslenir; komşuluk ÇİFT YÖNLÜdür.
        Çökük yollar komşuluk saymaz: oradan geçilemiyorsa ölüler de akmaz."""
        graf = {ad: set() for ad in self.places}
        for ad, place in self.places.items():
            for hedef in place.links or []:
                if hedef not in graf:
                    continue
                graf[ad].add(hedef)
                graf[hedef].add(ad)
        for road in self.roads:
            if not road.passable:
                continue
            if road.a in graf and road.b in graf:
                graf[road.a].add(road.b)
                graf[road.b].add(road.a)
        return {ad: sorted(komsular) for ad, komsular in graf.items()}

    # -------------------------------------------------------------- mesafe
    def coords(self, name: str):
        """Yerin (x, y) koordinatı — yoksa None."""
        place = self.places.get(name)
        if place is None:
            return None
        if isinstance(place.x, (int, float)) and isinstance(place.y, (int, float)):
            return (float(place.x), float(place.y))
        return None

    def straight_km(self, a: str, b: str):
        """Kuş uçuşu mesafe (km). Koordinat yoksa None.

        Yolun gerçek uzunluğu bundan uzundur; bu değer "ne kadar uzakta"
        sorusunun ham cevabıdır, "nasıl gidilir"in değil."""
        p, q = self.coords(a), self.coords(b)
        if p is None or q is None:
            return None
        return round(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5, 2)

    def roads_between(self, a: str, b: str) -> list:
        """İki yer arasındaki TÜM yollar — sıfır, bir ya da birkaç tane."""
        return [r for r in self.roads
                if (r.a == a and r.b == b) or (r.a == b and r.b == a)]

    def roads_of(self, name: str) -> list:
        return [r for r in self.roads if name in (r.a, r.b)]

    def route(self, a: str, b: str, avoid_blocked: bool = True):
        """En kısa rota (Dijkstra). Dönen:

            {"km": toplam, "hops": [yer adları], "roads": [Road], "risk": en yüksek}

        Ulaşılamıyorsa None. Maliyet yolun km'si × durum çarpanıdır: tıkalı bir
        yol daha uzun sayılır, çökük yol hiç kullanılmaz. Böylece "birden fazla
        yol" gerçekten bir seçime dönüşür — kısa ve tehlikeli mi, uzun ve
        sessiz mi.
        """
        if a == b:
            return {"km": 0.0, "hops": [a], "roads": [], "risk": 0}
        if a not in self.places or b not in self.places:
            return None
        import heapq

        komsuluk = {}
        for road in self.roads:
            if avoid_blocked and not road.passable:
                continue
            if road.a not in self.places or road.b not in self.places:
                continue
            komsuluk.setdefault(road.a, []).append(road)
            komsuluk.setdefault(road.b, []).append(road)

        kuyruk = [(0.0, a, [a], [])]
        gorulen = {}
        while kuyruk:
            maliyet, dugum, yol, kullanilan = heapq.heappop(kuyruk)
            if dugum == b:
                gercek = sum(float(r.km or 0) for r in kullanilan)
                riskler = [int(r.risk or 0) for r in kullanilan]
                return {"km": round(gercek, 2), "hops": yol,
                        "roads": kullanilan, "risk": max(riskler) if riskler else 0}
            if dugum in gorulen and gorulen[dugum] <= maliyet:
                continue
            gorulen[dugum] = maliyet
            for road in komsuluk.get(dugum, []):
                hedef = road.other(dugum)
                if hedef is None or hedef in yol:
                    continue
                heapq.heappush(kuyruk, (maliyet + road.cost(), hedef,
                                        yol + [hedef], kullanilan + [road]))
        return None

    def distances_from(self, name: str, names=None) -> list:
        """Bir yerden diğerlerine mesafeler, yakından uzağa.

        [{"ad", "km", "kus_ucusu", "hops", "risk", "yol"}]. `km` rotanın
        gerçek uzunluğu; rota yoksa None döner ama kuş uçuşu yine verilir —
        "oraya yol yok ama şu kadar uzakta" bilgisi de bir bilgidir."""
        hedefler = list(names) if names is not None else list(self.places)
        satirlar = []
        for hedef in hedefler:
            if hedef == name or hedef not in self.places:
                continue
            rota = self.route(name, hedef)
            satirlar.append({
                "ad": hedef,
                "km": rota["km"] if rota else None,
                "kus_ucusu": self.straight_km(name, hedef),
                "hops": max(0, len(rota["hops"]) - 1) if rota else None,
                "risk": rota["risk"] if rota else None,
                "yol": [r.kind for r in rota["roads"]] if rota else [],
            })
        satirlar.sort(key=lambda s: (s["km"] is None, s["km"] if s["km"] is not None
                                     else (s["kus_ucusu"] or 9e9)))
        return satirlar

    def add_road(self, a: str, b: str, kind: str, km: float, status: str = "açık",
                 risk: int = 2, notes: str = "") -> "Road":
        """Yeni yol ekler (aynı türde yol zaten varsa tekrarlamaz)."""
        for road in self.roads_between(a, b):
            if road.kind == kind:
                return road
        road = Road.new(a, b, kind, km, status, risk, notes)
        self.roads.append(road)
        self._touch("roads")
        return road

    def reveal_neighbours(self, name: str, level: str = "duyuldu") -> list:
        """Bir yere varınca yol komşuları en azından DUYULMUŞ olur.

        Bir mekana geldiğinde tabelaları, yol ağzını, karşı tepedeki binayı
        görürsün. Harita bütünüyle üretilmiş olduğu için bu, keşfin doğal
        biçimde açılmasını sağlar: gittiğin yer haritayı bir adım büyütür."""
        acilan = []
        for road in self.roads_of(name):
            komsu = road.other(name)
            place = self.places.get(komsu)
            if place is None or not place.hidden:
                continue
            place.raise_knowledge(level)
            road._set("known", "duyuldu")
            acilan.append(komsu)
        return acilan

    def keep_only(self, names) -> None:
        allowed = set(names or [])
        if self.party:
            self.party = {k: v for k, v in self.party.items() if k in allowed}

    def merge_patch(self, patch: dict, day=None) -> None:
        """state-update'in `map` alanı.

        Kabul edilen yazımlar:
          {"current": "Kuzey deposu"}
          {"places": {"Kuzey deposu": {"kind": "depo", "danger": "tehlikeli"}}}
          {"places_add": {...}}  (places ile aynı — model iki türlü de yazıyor)
          {"party": {"Okan": "Kuzey deposu"}}
          {"link": ["Kuzey deposu", "Su kulesi"]}
        """
        if not isinstance(patch, dict):
            return
        for key in ("places", "places_add", "places_update"):
            raw = patch.get(key)
            if not isinstance(raw, dict):
                continue
            self._touch("places")
            for name, fields in raw.items():
                if not isinstance(name, str) or not name.strip():
                    continue
                if isinstance(fields, str):       # {"Su kulesi": "yanmış"}
                    fields = {"status": fields}
                if not isinstance(fields, dict):
                    continue
                place = self.ensure_place(name.strip(), day)
                if place.discovered_day is None and day is not None:
                    place._set("discovered_day", day)
                place.merge_patch(fields)

        party = patch.get("party")
        if isinstance(party, dict):
            for name, where in party.items():
                self.place_person(name, where, day)

        links = patch.get("link") or patch.get("links")
        if isinstance(links, list) and len(links) == 2 and all(
                isinstance(x, str) for x in links):
            self.link(links[0], links[1])

        current = patch.get("current") or patch.get("location")
        if isinstance(current, str) and current.strip():
            self.go(current, day)

    def sync_from_world(self, location, characters: dict, day=None) -> None:
        """Model haritayı yazmayı unutsa bile konum bilgisi akmaya devam etsin:
        `location` ana konumu besler, `party`'de kaydı OLMAYAN karakterler de
        kişisel `location`'larına (yoksa ana konuma) yerleştirilir.

        Mevcut `party` kayıtlarının ÜZERİNE YAZMAZ: bu turda anlatıcı birini
        açıkça başka bir yere koyduysa (`map.party`) o kayıt geçerlidir. Aksi
        halde karakterin eskimiş `location` alanı, yeni yazılmış parti
        kaydını her turda geri alıyordu."""
        if isinstance(location, str) and location.strip() and location != self.current:
            self.go(location, day)
        for name, person in (characters or {}).items():
            if name in self.party:
                continue
            where = getattr(person, "location", None)
            if not (isinstance(where, str) and where.strip()):
                where = self.current
            if isinstance(where, str) and where.strip():
                self.place_person(name, where, day)
        self.keep_only(list((characters or {}).keys()))
