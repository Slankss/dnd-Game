"""Kişi kaydı — `characters` ve `npcs` için ortak gövde.

`_merge_person_like`'ın tamamı burada: künye alanları üzerine yazılır,
envanter birleştirilir (elden çıkan `lost_items`'a düşer), ilişkiler/vitals/
yaralar/sahne katılımı iç içe güncellenir.
"""

from dataclasses import dataclass, field

from .base import DictModel
from .inventory import CountedItems, metinden_say, sayilabilir
from .presence import PRESENCE_STATES, Presence
from .text import as_str_list, norm_tr
from .vitals import Vitals
from .wounds import HEALTHY_STATUSES, WoundList, status_for

# Kurulum ekranındaki künye alanları. `secret` oyuncu arayüzüne ASLA gitmez.
# `reflex` = karakterin baskı altındaki ilk tepkisi (küfreder, donar, saldırır…);
# felaket/kritik zar bantlarında anlatıcı bu refleksi FİİLEN oynatır.
SHEET_FIELDS = ("profession", "age", "strength", "weakness", "reflex", "secret")
SECRET_FIELD = "secret"
REFLEX_FIELD = "reflex"

# Üzerine yazılan düz metin alanları (`_merge_person_like`'daki sıra).
SCALAR_FIELDS = ("background", "traits", "status", "location", "notes") + SHEET_FIELDS

# Tanınmadık bir isim için açılan boş kaydın anahtar sırası.
NEW_PERSON_ORDER = ("background", "traits", "status", "alive", "location",
                    "inventory", "relationships", "notes")


def build_background(char) -> str:
    """Künyeden okunabilir bir `background` cümlesi kurar — anlatıcı ve
    kenar çubuğu bu alanı kullanıyor."""
    age, profession = char.get("age"), char.get("profession")
    parts = []
    if age:
        parts.append(f"{age} yaşında")
    if profession:
        parts.append(profession)
    return ", ".join(parts)


def build_traits(char) -> str:
    parts = []
    if char.get("strength"):
        parts.append(f"Güçlü yanı: {char['strength']}")
    if char.get("weakness"):
        parts.append(f"Zayıf yanı: {char['weakness']}")
    if char.get("reflex"):
        parts.append(f"Refleksi: {char['reflex']}")
    return " · ".join(parts)


@dataclass
class Person(DictModel):
    """`world_state.characters.<isim>` / `world_state.npcs.<isim>`."""

    KNOWN = SHEET_FIELDS + ("background", "traits", "status", "alive", "location",
                            "notes", "inventory", "inventory_counts", "lost_items",
                            "relationships", "wounds", "vitals", "presence")

    profession: object = None
    age: object = None
    strength: object = None
    weakness: object = None
    reflex: object = None
    secret: object = None
    background: object = None
    traits: object = None
    status: object = None
    alive: object = None
    location: object = None
    notes: object = None
    inventory: list = field(default_factory=list)
    # Sayılabilir kalemlerin miktarı ({"9mm fişek": 12}). Sunucu tutar,
    # anlatıcı muhasebe yapmaz — bkz. models/inventory.py.
    inventory_counts: dict = field(default_factory=dict)
    lost_items: list = field(default_factory=list)
    relationships: dict = field(default_factory=dict)
    wounds: object = None      # None = kayıtta yok (eski NPC'lerde olabiliyor)
    vitals: object = None      # None = takip edilmiyor (NPC'ler için normal)
    presence: object = None
    extra: dict = field(default_factory=dict)
    key_order: list = field(default_factory=list)

    # ------------------------------------------------------------ dönüşüm
    @classmethod
    def from_dict(cls, data: dict) -> "Person":
        data = data or {}
        person = cls()
        person.extra, person.key_order = cls._split(data)
        for name in SHEET_FIELDS + ("background", "traits", "status", "alive",
                                    "location", "notes"):
            setattr(person, name, data.get(name))
        # Beklenmedik tipteki alanlar `extra`'ya düşer: modelin yapısını
        # bozamayız ama kaydı da atamayız.
        for name, kind in (("inventory", list), ("lost_items", list),
                           ("inventory_counts", dict), ("relationships", dict)):
            raw = data.get(name)
            if isinstance(raw, kind):
                setattr(person, name, kind(raw))
            elif name in data:
                person.extra[name] = raw
        if isinstance(data.get("wounds"), list):
            person.wounds = WoundList.from_list(data["wounds"])
        elif "wounds" in data:
            person.extra["wounds"] = data["wounds"]
        if isinstance(data.get("vitals"), dict):
            person.vitals = Vitals.from_dict(data["vitals"])
        elif "vitals" in data:
            person.extra["vitals"] = data["vitals"]
        if isinstance(data.get("presence"), dict):
            person.presence = Presence.from_dict(data["presence"])
        elif "presence" in data:
            person.extra["presence"] = data["presence"]
        person._backfill_counts()
        return person

    def _backfill_counts(self) -> None:
        """Envanterdeki sayıyı sayaca taşır: "12 9mm fişek" → "9mm fişek" ×12.

        Devam eden oyunlar (ve anlatıcının serbest yazdığı eşyalar) miktarı
        ismin içine gömüyor. Sayı iki yerde durursa biri eskir — bu yüzden
        isim listesinde SADE ad, miktar sayaçta tutulur.
        """
        if not self.inventory:
            return
        counted = CountedItems(self.inventory_counts)
        degisti = False
        for i, item in enumerate(list(self.inventory)):
            if not isinstance(item, str):
                continue
            ad, adet = metinden_say(item)
            if adet is None or not ad or not sayilabilir(ad):
                continue
            self.inventory[i] = ad
            if counted.find(ad) is None:
                counted.set(ad, adet)
            degisti = True
        if degisti:
            self._touch("inventory_counts")
            self.inventory_counts = counted.to_dict()
        # Sayacı olup listede görünmeyen kalem eklenir: oyuncu envanterinde
        # "9mm fişek"i görmeli, sayaç arayüzde onun yanına yazılıyor.
        var = {norm_tr(i) for i in self.inventory if isinstance(i, str)}
        for ad in counted.items:
            if norm_tr(ad) not in var:
                self.inventory.append(ad)
                self._touch("inventory")

    @classmethod
    def new(cls) -> "Person":
        """`_merge_person_like`'ın tanımadık isim için açtığı boş kayıt."""
        person = cls(background=None, traits=None, status="İyi", alive=True,
                     location=None, inventory=[], relationships={}, notes="")
        person.key_order = list(NEW_PERSON_ORDER)
        return person

    def to_dict(self) -> dict:
        values = {name: getattr(self, name) for name in
                  SHEET_FIELDS + ("background", "traits", "status", "alive",
                                  "location", "notes")}
        values["inventory"] = self.inventory
        # Boş sayaç sözlüğü kayda yazılmaz (`_emit` boş değerleri eler):
        # sayılabilir eşyası olmayan künye boş bir alanla şişmesin.
        values["inventory_counts"] = self.inventory_counts
        values["lost_items"] = self.lost_items
        values["relationships"] = self.relationships
        if self.wounds is not None:
            values["wounds"] = self.wounds.to_list()
        if self.vitals is not None:
            values["vitals"] = self.vitals.to_dict()
        if self.presence is not None:
            values["presence"] = self.presence.to_dict()
        return self._emit(values)

    # ------------------------------------------------------------- durum
    @property
    def is_alive(self) -> bool:
        """`entry.get("alive", True)` karşılığı — alan hiç yoksa hayattadır."""
        return bool(self.alive) if "alive" in self.key_order else True

    @property
    def explicitly_dead(self) -> bool:
        """`entry.get("alive") is False` karşılığı (drift/enfeksiyon atlama)."""
        return self.alive is False

    @property
    def presence_state(self) -> str:
        if self.presence is None or self.presence.state not in PRESENCE_STATES:
            return "sahnede"
        return self.presence.state

    def ensure_vitals(self) -> Vitals:
        if self.vitals is None:
            self.vitals = Vitals.default()
        self._touch("vitals")
        return self.vitals.normalize()

    def ensure_presence(self) -> Presence:
        if self.presence is None:
            self.presence = Presence.default()
        self._touch("presence")
        return self.presence.normalize()

    def ensure_wounds(self) -> WoundList:
        if self.wounds is None:
            self.wounds = WoundList()
        self._touch("wounds")
        return self.wounds

    # ---------------------------------------------------------- birleştirme
    def merge_patch(self, fields: dict, day=None, clock=None) -> set:
        """Anlatıcının bu turda elle yazdığı `vitals` alanlarını döndürür —
        otomatik artıştan muaf tutulurlar."""
        for scalar_key in SCALAR_FIELDS:
            if scalar_key in fields:
                self._set(scalar_key, fields[scalar_key])

        if isinstance(fields.get("alive"), bool):
            self._set("alive", fields["alive"])

        if isinstance(fields.get("relationships"), dict):
            self._touch("relationships")
            self.relationships.update(fields["relationships"])

        self.merge_presence(fields, day, clock)
        self.ensure_wounds().merge_patch(fields, day, clock)
        self.merge_inventory(fields)

        touched = set()
        if isinstance(fields.get("vitals"), dict):
            touched = self.ensure_vitals().merge_patch(fields["vitals"])
        return touched

    def merge_presence(self, fields: dict, day=None, clock=None) -> None:
        """Düz string de kabul edilir ("presence": "uyuyor")."""
        raw = fields.get("presence")
        if isinstance(raw, str):
            raw = {"state": raw}
        if not isinstance(raw, dict):
            return
        self.ensure_presence().merge_patch(raw, day, clock)

    # ------------------------------------------------------ sayılabilir stok
    def counts(self) -> CountedItems:
        """Sayaç sarmalayıcısı. Değişiklikler `store_counts` ile geri yazılır."""
        return CountedItems(self.inventory_counts)

    def store_counts(self, counted: CountedItems) -> None:
        """Sayaçları geri yazar ve tükenen kalemi envanterden düşürür.

        Sayacı biten kalem cepte "var" görünmemeli: "9mm fişek" yazısı duruyor
        ama sayacı 0 olan bir kayıt, düzeltmeye çalıştığımız tutarsızlığın ta
        kendisi olurdu. Tükenen kalem `lost_items`'a geçer, böylece model
        sonraki turda hafızasından geri yazamaz."""
        # Hangi kalemler SAYILIYORDU — üzerine yazmadan önce saptanır.
        sayiliyordu = {norm_tr(ad) for ad in self.inventory_counts}
        self._touch("inventory_counts")
        self.inventory_counts = counted.to_dict()
        self._touch("lost_items")
        for item in list(self.inventory):
            if not isinstance(item, str) or not sayilabilir(item):
                continue
            ad = metinden_say(item)[0] or item
            if counted.count(ad) > 0:
                continue
            if counted.find(ad) is None and norm_tr(ad) not in sayiliyordu:
                continue  # hiç sayılmamış kalem: dokunma
            self.inventory[:] = [i for i in self.inventory if i is not item]
            if all(norm_tr(i) != norm_tr(item) for i in self.lost_items):
                self.lost_items.append(item)

    def spend_item(self, name, amount: int) -> int:
        """Kalemden `amount` kadar harca; GERÇEKTEN harcananı döndür."""
        counted = self.counts()
        harcanan = counted.spend(name, amount)
        if harcanan:
            self.store_counts(counted)
        return harcanan

    def count_of(self, name) -> int:
        return self.counts().count(name)

    def merge_inventory(self, fields: dict) -> None:
        self._touch("inventory")
        inv = self.inventory
        # Elden çıkmış eşyaların kaydı. Model sonraki turlarda hafızasından TAM
        # listeyi tekrar yazınca (atılan madalyonu içeren eski liste gibi) eşya
        # sessizce cebe geri dönüyordu — hikaye tutarsızlaşıyordu. Bir eşya ancak
        # sahnede FİİLEN geri alınırsa (`inventory_add`) bu listeden çıkar.
        self._touch("lost_items")
        lost = self.lost_items
        lost_keys = {norm_tr(i) for i in lost}

        # Sayılabilir kalemlerde miktar İSİMDEN ayrılır: "12 fişek" listeye
        # "fişek" olarak girer, 12 sayaca yazılır. Sayı iki yerde dursaydı biri
        # eskir ve envanter yine tutarsızlaşırdı.
        eklenen_sayilar = {}
        added = self._strip_counts(as_str_list(fields.get("inventory_add")),
                                   eklenen_sayilar)
        bulk = self._strip_counts(as_str_list(fields.get("inventory")),
                                  eklenen_sayilar)
        removed = self._strip_counts(as_str_list(fields.get("inventory_remove")), {})

        # açık geri alma: eşya tekrar sahiplenildi
        for item in added:
            key = norm_tr(item)
            if key in lost_keys:
                lost_keys.discard(key)
                lost[:] = [i for i in lost if norm_tr(i) != key]

        # Model bazen `inventory_add` yerine doğrudan tam listeyi (`inventory`)
        # ya da tek bir eşyayı düz string olarak yazıyor; üçü de kabul ediliyor.
        # `inventory` üzerine YAZMAZ, birleştirir (model listeyi eksik yazarsa
        # mevcut eşyalar kaybolmasın) — ama elden çıkmış eşyayı geri getiremez.
        added_keys = {norm_tr(i) for i in added}
        for item in bulk + added:
            if not item or item in inv:
                continue
            key = norm_tr(item)
            if key in lost_keys and key not in added_keys:
                continue
            inv.append(item)

        for item in removed:
            key = norm_tr(item)
            inv[:] = [i for i in inv if norm_tr(i) != key]
            if key not in lost_keys:
                lost.append(item)
                lost_keys.add(key)

        self._merge_counts(fields, eklenen_sayilar, removed)

    @staticmethod
    def _strip_counts(items: list, sayilar: dict) -> list:
        """"12 fişek" → "fişek" (+ sayilar["fişek"] += 12). Sayısızlar aynen."""
        sade = []
        for item in items:
            ad, adet = metinden_say(item)
            if adet is not None and ad and sayilabilir(ad):
                sayilar[ad] = sayilar.get(ad, 0) + adet
                sade.append(ad)
            else:
                sade.append(item)
        return sade

    def _merge_counts(self, fields: dict, eklenen: dict, removed: list) -> None:
        """Sayılabilir kalemlerin miktarını günceller.

        Üç kaynak: (1) eklenen eşyanın adındaki sayı ("12 fişek"),
        (2) çıkarılan eşyanın sayacının silinmesi, (3) anlatıcının açık
        `inventory_counts` yaması — en son o uygulanır, çünkü kesin miktar
        beyanıdır. Miktar bilinmiyorsa UYDURULMAZ: sayaç açılmaz, kalem eskisi
        gibi sayısız durur."""
        counted = self.counts()
        degisti = False

        for ad, adet in eklenen.items():
            counted.add(ad, adet)
            degisti = True

        for item in removed:
            mevcut = counted.find(item)
            if mevcut:
                counted.drop(mevcut)
                degisti = True

        ham = fields.get("inventory_counts")
        if isinstance(ham, dict):
            for ad, adet in ham.items():
                if isinstance(ad, str) and ad.strip():
                    counted.set(ad, adet)
                    degisti = True

        if degisti:
            self.store_counts(counted)
            # Sayacı olan ama isim listesinde görünmeyen kalem eklenir:
            # oyuncu envanterinde "9mm fişek"i görmeli.
            var = {norm_tr(i) for i in self.inventory}
            for ad in counted.items:
                if norm_tr(ad) not in var:
                    self.inventory.append(ad)

    # ------------------------------------------------------ tur bakımı
    def apply_vitals_drift(self, hours: float, touched=()) -> None:
        self.ensure_vitals().drift(hours, self.presence_state == "uyuyor", touched)

    def advance_infections(self, hours: float) -> None:
        if self.wounds is not None:
            self.wounds.advance_infection(hours)

    def normalize_wound_status(self) -> None:
        wounds = self.wounds.wounds() if self.wounds is not None else []
        if not wounds:
            return
        if norm_tr(self.status) not in HEALTHY_STATUSES:
            return
        self._set("status", status_for(wounds))
