"""Sayılabilir envanter — mermi, sargı, batarya, su…

Sorun: `Person.inventory` düz bir isim listesidir. "9mm fişek" ya listededir ya
değildir; miktar kavramı yoktur. Bu yüzden silah sıkılınca mermi azalmıyordu —
kusursuz bir anlatıcı bile "12 → 9" yazamazdı, yazacak alan yoktu.

Çözüm: isim listesinin yanında **sunucunun tuttuğu** bir sayaç sözlüğü
(`Person.inventory_counts`). Anlatıcı muhasebe tutmaz; seçeneğin `spend` alanı
neyin harcandığını beyan eder, sunucu keser (bkz. `services/inventory_service`).

Kurallar:

* Her eşya sayılmaz. "el feneri" tektir, sayaç istemez; "fişek" sayılır.
  `sayilabilir()` bunu anahtar kelimeden karar verir.
* İsimler Türkçeye duyarlı eşleşir: "9mm Mermi" ile "9mm mermi" aynı kalemdir
  (`anahtar`), yoksa aynı şeyin iki sayacı olurdu.
* Sayaç sıfıra inince kalem envanterden de düşer ve `lost_items`'a geçer:
  "fişek" yazısı cepte kalıp sayacı 0 gösteren bir kayıt en kafa karıştırıcı
  haldir.
* Serbest metinden sayı okunur: anlatıcı "12 fişek" ya da "9mm fişek x2" diye
  yazdığında sayaç kendiliğinden doğar (`metinden_say`).
"""

import re

from .text import norm_tr

#: Sayılabilir kalem anahtar kelimeleri — kök eşleşmesiyle aranır ("fişekler",
#: "fişeği" de tutar). Sıra önemsiz; herhangi biri tutarsa kalem sayılabilirdir.
COUNTABLE_WORDS = (
    "fişek", "mermi", "kurşun", "şarjör", "saçma", "ok ", "cephane",
    "sargı", "bandaj", "gazlı bez", "dikiş", "ilaç", "antibiyotik", "ağrı kesici",
    "serum", "iğne", "tablet", "hap",
    "batarya", "pil", "yakıt", "benzin", "mazot", "gaz",
    "su", "konserve", "kutu", "paket", "erzak", "yiyecek", "tayın",
    "kibrit", "çakmak gazı", "mum", "fener camı", "filtre", "kablo bağı",
)

#: "12 fişek", "9mm fişek x2", "fişek (7)", "3 adet sargı"
_SAYI_ONDE = re.compile(r"^\s*(\d{1,4})\s*(?:adet|tane|x)?\s+(.*\S)\s*$", re.I)
_SAYI_ARKADA = re.compile(r"^\s*(.*?\S)\s*(?:[x×]\s*(\d{1,4})|\((\d{1,4})\s*(?:adet|tane)?\))\s*$", re.I)

#: Mermi/cephane — otomatik tüketim bunu arar.
AMMO_WORDS = ("fişek", "mermi", "kurşun", "saçma", "cephane")


def anahtar(name) -> str:
    """Kalem adının eşleşme anahtarı (Türkçeye duyarlı, boşluk normalize)."""
    return norm_tr(name or "")


def _kok_gecer(metin: str, kelimeler) -> bool:
    """Anahtar kelimelerden biri metinde kök olarak geçiyor mu.

    Türkçe ekler yüzünden düz `in` yetmiyor: "fişeğim" içinde "fişek" yok
    (k→ğ yumuşaması). Kökün son bir-iki harfi düşürülerek aranır.
    """
    hedef = norm_tr(metin)
    if not hedef:
        return False
    for kelime in kelimeler:
        kok = norm_tr(kelime)
        if not kok:
            continue
        if kok in hedef:
            return True
        kisa = kok[: max(3, len(kok) - 1)]
        if len(kisa) >= 4 and kisa in hedef:
            return True
    return False


def sayilabilir(name) -> bool:
    """Bu kalem miktarla mı takip edilmeli?"""
    return _kok_gecer(name, COUNTABLE_WORDS)


def cephane_mi(name) -> bool:
    """Bu kalem mermi/cephane mi (otomatik tüketim için)?"""
    return _kok_gecer(name, AMMO_WORDS)


def metinden_say(text):
    """"12 fişek" → ("fişek", 12) · "9mm fişek x2" → ("9mm fişek", 2).

    Sayı yoksa (ad, None) döner: kalem sayılabilir olsa bile miktarı bilinmiyor
    demektir, uydurmayız."""
    ham = str(text or "").strip()
    if not ham:
        return "", None
    m = _SAYI_ONDE.match(ham)
    if m:
        return m.group(2).strip(), int(m.group(1))
    m = _SAYI_ARKADA.match(ham)
    if m:
        adet = m.group(2) or m.group(3)
        return m.group(1).strip(), int(adet)
    return ham, None


def as_count(value, current: int = 0):
    """Sayaç değeri: kesin sayı (12), göreli değişim ("-3"/"+9") ya da None.

    `resources.ResourceItem.apply_value` ile aynı sözleşme — anlatıcı iki
    biçimi de yazıyor, ikisini de kabul ediyoruz."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        ham = value.strip()
        m = re.match(r"^([+-])\s*(\d+)$", ham)
        if m:
            delta = int(m.group(2))
            return max(0, current + (delta if m.group(1) == "+" else -delta))
        if ham.isdigit():
            return max(0, int(ham))
    return None


class CountedItems:
    """`{kalem adı: adet}` — Türkçeye duyarlı anahtarla çalışan ince sarmalayıcı.

    Sözlüğün kendisi `Person.inventory_counts` içinde durur ve state.json'a
    olduğu gibi yazılır; bu sınıf sadece eşleşme/aritmetik kurallarını taşır.
    """

    def __init__(self, data=None):
        self.items = {}
        for ad, adet in (data or {}).items():
            if not isinstance(ad, str) or not ad.strip():
                continue
            sayi = as_count(adet)
            if sayi is not None:
                self.items[ad.strip()] = sayi

    # ------------------------------------------------------------- okuma
    def to_dict(self) -> dict:
        return dict(self.items)

    def key_for(self, name):
        """Kayıttaki gerçek anahtar (büyük/küçük harf farkı yutulur)."""
        hedef = anahtar(name)
        for ad in self.items:
            if anahtar(ad) == hedef:
                return ad
        return None

    def find(self, name):
        """Adı geçen ilk kalem — tam eşleşme yoksa içeren/içerilen aranır.

        "fişek" istendiğinde "9mm fişek" bulunsun diye: seçenek bedeli genel
        ("fişek"), envanter özel ("9mm fişek") yazılmış olabilir."""
        tam = self.key_for(name)
        if tam:
            return tam
        hedef = anahtar(name)
        if not hedef:
            return None
        for ad in self.items:
            mevcut = anahtar(ad)
            if hedef in mevcut or mevcut in hedef:
                return ad
        return None

    def count(self, name) -> int:
        ad = self.find(name)
        return int(self.items.get(ad, 0)) if ad else 0

    def ammo_keys(self) -> list:
        """Cephane kalemleri, çoktan aza — otomatik tüketim buradan seçer."""
        return sorted((ad for ad in self.items if cephane_mi(ad)),
                      key=lambda ad: -self.items[ad])

    # -------------------------------------------------------------- yazma
    def set(self, name, adet) -> None:
        ad = self.key_for(name) or str(name).strip()
        if not ad:
            return
        sayi = as_count(adet, self.items.get(ad, 0))
        if sayi is None:
            return
        if sayi <= 0:
            self.items.pop(ad, None)
        else:
            self.items[ad] = sayi

    def add(self, name, adet: int) -> None:
        ad = self.find(name) or str(name).strip()
        if not ad or not adet:
            return
        self.items[ad] = max(0, self.items.get(ad, 0) + int(adet))
        if not self.items[ad]:
            self.items.pop(ad, None)

    def spend(self, name, adet: int) -> int:
        """`adet` kadar harcamayı dener; GERÇEKTEN harcanan sayıyı döndürür.

        Eksik varsa var olan kadarı harcanır (0 da olabilir). Çağıran farkı
        görüp "mermi yetmedi" sahnesini kurabilsin diye sessizce sıfırlamaz."""
        ad = self.find(name)
        if not ad or adet <= 0:
            return 0
        mevcut = int(self.items.get(ad, 0))
        harcanan = min(mevcut, int(adet))
        kalan = mevcut - harcanan
        if kalan:
            self.items[ad] = kalan
        else:
            self.items.pop(ad, None)
        return harcanan

    def drop(self, name) -> None:
        ad = self.key_for(name)
        if ad:
            self.items.pop(ad, None)


def normalize_spend(value) -> dict:
    """Seçeneğin `spend` alanını `{kalem: pozitif adet}` haline getirir.

    Kabul edilen biçimler:
      {"9mm fişek": 2}          · sözlük (asıl biçim)
      {"9mm fişek": "2"}        · sayı string olarak
      ["9mm fişek", "sargı"]    · liste → her biri 1 adet
      "9mm fişek"               · tek kalem → 1 adet
    """
    if isinstance(value, str):
        ad, adet = metinden_say(value)
        return {ad: max(1, adet or 1)} if ad else {}
    if isinstance(value, list):
        out = {}
        for ham in value:
            if isinstance(ham, str) and ham.strip():
                ad, adet = metinden_say(ham)
                if ad:
                    out[ad] = out.get(ad, 0) + max(1, adet or 1)
        return out
    if isinstance(value, dict):
        out = {}
        for ad, adet in value.items():
            if not isinstance(ad, str) or not ad.strip():
                continue
            sayi = as_count(adet)
            if sayi is None:
                _, sayi = metinden_say(str(adet))
            if sayi and sayi > 0:
                out[ad.strip()] = int(sayi)
        return out
    return {}
