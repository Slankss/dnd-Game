"""Sabit eşya kataloğu — `data/items.json`.

Katalog HER OYUNDA AYNIDIR: 9mm tabanca her oyunda 9mm tabancadır, karakolda
bulunma ihtimali yüksek, metroda çok düşüktür. Bu, oyunun mekanik omurgasıdır
ve anlatıcının uydurmasına bırakılmaz.

İki tür eşya vardır ve karıştırılmamalıdır:

  **Katalog eşyası** (bu dosya) — mekaniği vardır: yiyeceğin `doyum`u açlığı
  düşürür, menzilli silahın `mermi`si envanterden kesilir, bulunma ağırlığı
  aramayı belirler.

  **Hikaye eşyası** (`world_state.story_items`) — anlatıcı üretir, her oyunda
  farklıdır ve YALNIZCA anlatı etkisi taşır. Ne açlık doldurur ne zar değiştirir;
  sahnede anlamı vardır, tabloda yeri yoktur.

Yer türü eşleşmesi tehdit motoruyla aynı mantıktadır (`threat.density_of`):
yer ADI Türkçeye duyarlı biçimde normalize edilir ve anahtar kelimeler kök
olarak aranır ("Aile sağlığı merkezi" → `hastane`). En uzun eşleşme kazanır,
hiçbiri tutmazsa eşya `taban` ağırlığıyla değerlendirilir.
"""

from dataclasses import dataclass, field

from .text import norm_tr

#: Nadirlik → arama zarındaki çarpan. Ağırlıklar zaten yere özel, bu ikinci
#: bir fren: çok nadir eşya doğru yerde bile kolay çıkmasın.
RARITY_FACTOR = {"yaygın": 1.0, "nadir": 0.55, "çok nadir": 0.22}



@dataclass
class Item:
    """Katalogdaki tek bir eşya."""

    id: str = ""
    ad: str = ""
    kategori: str = ""
    nadirlik: str = "yaygın"
    taban: int = 0
    bulunur: dict = field(default_factory=dict)
    ikinci_kategori: str = ""
    mermi: str = ""             # menzilli silahın harcadığı mühimmat adı
    sayilabilir: bool = False
    adet: tuple = (1, 1)        # bulunduğunda çıkan adet aralığı
    doyum: int = 0              # açlığı bu kadar düşürür (0-100)
    susuzluk: int = 0           # susuzluğu bu kadar düşürür (0-100)
    aciklama: str = ""

    @classmethod
    def from_dict(cls, data) -> "Item":
        data = data if isinstance(data, dict) else {}
        ham_adet = data.get("adet")
        if isinstance(ham_adet, list) and len(ham_adet) == 2:
            adet = (int(ham_adet[0]), int(ham_adet[1]))
        else:
            adet = (1, 1)
        bulunur = data.get("bulunur")
        return cls(
            id=str(data.get("id") or ""),
            ad=str(data.get("ad") or ""),
            kategori=str(data.get("kategori") or ""),
            nadirlik=str(data.get("nadirlik") or "yaygın"),
            taban=int(data.get("taban") or 0),
            bulunur=dict(bulunur) if isinstance(bulunur, dict) else {},
            ikinci_kategori=str(data.get("ikinci_kategori") or ""),
            mermi=str(data.get("mermi") or ""),
            sayilabilir=bool(data.get("sayilabilir")),
            adet=adet,
            doyum=int(data.get("doyum") or 0),
            susuzluk=int(data.get("susuzluk") or 0),
            aciklama=str(data.get("not") or ""),
        )

    def to_dict(self) -> dict:
        out = {"id": self.id, "ad": self.ad, "kategori": self.kategori,
               "nadirlik": self.nadirlik}
        if self.mermi:
            out["mermi"] = self.mermi
        if self.sayilabilir:
            out["sayilabilir"] = True
        if self.doyum:
            out["doyum"] = self.doyum
        if self.susuzluk:
            out["susuzluk"] = self.susuzluk
        if self.aciklama:
            out["not"] = self.aciklama
        return out

    # ------------------------------------------------------------- sorgular
    @property
    def yiyecek_mi(self) -> bool:
        return self.doyum > 0

    @property
    def icecek_mi(self) -> bool:
        return self.susuzluk > 0

    def weight_at(self, archetype: str) -> float:
        """Bu yer türünde bulunma ağırlığı (nadirlik çarpanı uygulanmış)."""
        ham = self.bulunur.get(archetype)
        if ham is None:
            ham = self.taban
        return max(0.0, float(ham)) * RARITY_FACTOR.get(self.nadirlik, 1.0)


class ItemCatalog:
    """`data/items.json`'ın okunmuş hali. Salt okunur; oyun onu değiştirmez."""

    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        self.surum = int(data.get("surum") or 0)
        yerler = data.get("yer_turleri")
        self.yer_turleri = yerler if isinstance(yerler, dict) else {}
        kategoriler = data.get("kategoriler")
        self.kategoriler = kategoriler if isinstance(kategoriler, dict) else {}
        ham = data.get("esyalar")
        self.items = [Item.from_dict(x) for x in ham] if isinstance(ham, list) else []
        self._by_key = {}
        for item in self.items:
            self._by_key.setdefault(norm_tr(item.ad), item)
            self._by_key.setdefault(norm_tr(item.id), item)

    def __len__(self) -> int:
        return len(self.items)

    # ----------------------------------------------------------- eşleşme
    def find(self, name):
        """Ada ya da id'ye göre eşya. Türkçeye duyarlı, ek toleranslı."""
        anahtar = norm_tr(name)
        if not anahtar:
            return None
        dogrudan = self._by_key.get(anahtar)
        if dogrudan is not None:
            return dogrudan
        # "9mm fişek" ararken "fişek" yazılmış olabilir (ya da tersi).
        en_iyi, en_uzun = None, 0
        for item in self.items:
            ad = norm_tr(item.ad)
            if not ad:
                continue
            if (ad in anahtar or anahtar in ad) and len(ad) > en_uzun:
                en_iyi, en_uzun = item, len(ad)
        return en_iyi

    def archetype_of(self, place_name: str, kind: str = "") -> str:
        """Yer adından (ve varsa türünden) katalog yer türü. Yoksa ""."""
        hedef = norm_tr(f"{place_name or ''} {kind or ''}")
        if not hedef:
            return ""
        kelimeler = hedef.split()
        en_iyi, en_uzun = "", 0
        for tur, bilgi in self.yer_turleri.items():
            for anahtar in (bilgi or {}).get("anahtar") or []:
                kok = norm_tr(anahtar)
                if not kok or len(kok) <= en_uzun:
                    continue
                # Türkçe ekler: "istasyonu" içinde "istasyon" var ama
                # "sağlığı" içinde "sağlık" yok — kökün sonu kırpılarak aranır.
                kisa = kok[: max(4, len(kok) - 2)]
                if kok in hedef or any(k.startswith(kisa) for k in kelimeler):
                    en_iyi, en_uzun = tur, len(kok)
        return en_iyi

    def place_label(self, archetype: str) -> str:
        return ((self.yer_turleri.get(archetype) or {}).get("ad")
                or archetype or "tanımsız yer")

    # ------------------------------------------------------------- havuz
    def candidates(self, archetype: str) -> list:
        """[(item, ağırlık)] — ağırlığı sıfır olanlar elenir."""
        havuz = []
        for item in self.items:
            agirlik = item.weight_at(archetype)
            if agirlik > 0:
                havuz.append((item, agirlik))
        return havuz

    def by_category(self, kategori: str) -> list:
        return [i for i in self.items
                if kategori in (i.kategori, i.ikinci_kategori)]

    def ammo_for(self, weapon_name: str) -> str:
        """Silahın harcadığı mühimmatın adı ("" = mühimmat istemiyor)."""
        item = self.find(weapon_name)
        return item.mermi if item is not None else ""
