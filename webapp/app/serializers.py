"""Dış dünyaya gidecek görünümler.

Anlatıcı gerçeği (`disposition`, `notes`, `gm_notes`, dünya zarı, sırlar) ile
oyuncunun bildiği ayrı iki katmandır. Oyuncuya giden HER gövde buradan geçer;
başka hiçbir yerde world_state doğrudan serileştirilmez.
"""

import time

from app.models.person import SECRET_FIELD
from app.models.round import Round
from app.models.world import GM_ONLY_FIELDS
from app.models.worldmap import knowledge_of, public_place, public_roads


def public_world_state(world_state: dict) -> dict:
    """Oyuncu arayüzüne gidecek, gizli alanları ayıklanmış kopya."""
    public = {k: v for k, v in world_state.items() if k not in GM_ONLY_FIELDS}
    # Karakter künyesindeki `secret` sadece anlatıcıya aittir — diğer
    # oyuncular aynı ekranı paylaştığı için buradan tamamen çıkarılır.
    for section in ("characters", "npcs"):
        people = public.get(section)
        if isinstance(people, dict):
            public[section] = {
                name: {k: v for k, v in (info or {}).items() if k != SECRET_FIELD}
                for name, info in people.items()
            }
    world_map = public.get("map")
    if isinstance(world_map, dict):
        # Harita da iki katmanlıdır: oyuncular yalnız ÖĞRENDİKLERİ kadarını
        # görür. Duyulmuş ama gidilmemiş bir yerin türü/tehlikesi/notu bu
        # gövdeye hiç girmez (bkz. models/worldmap.public_place).
        places = world_map.get("places")
        gorunur = {}
        if isinstance(places, dict):
            for name, info in places.items():
                govde = public_place(info)
                # `None` = grubun henüz duymadığı yer: haritada HİÇ yok.
                if govde is not None:
                    gorunur[name] = govde
        public["map"] = {
            **world_map,
            "places": gorunur,
            "roads": public_roads(world_map.get("roads"), set(gorunur)),
        }

    threat = public.get("threat")
    if isinstance(threat, dict):
        public["threat"] = public_threat(threat, world_map if isinstance(world_map, dict) else {})

    challenges = public.get("challenges")
    if isinstance(challenges, dict):
        # zorluklar oyunculara görünür ama her zorluğun gm_notes'u görünmez
        public["challenges"] = {
            name: {k: v for k, v in (info or {}).items() if k != "gm_notes"}
            for name, info in challenges.items()
        }
    factions = public.get("factions")
    if isinstance(factions, dict):
        # Fraksiyonun GERÇEK tavrı (disposition/notes) anlatıcıya özeldir;
        # oyuncular sadece öğrendiklerini (known/public_notes) görür.
        public["factions"] = {
            name: {
                "disposition": (info or {}).get("known") or "bilinmiyor",
                "notes": (info or {}).get("public_notes") or "",
            }
            for name, info in factions.items()
        }
    return public


def public_threat(threat: dict, world_map: dict) -> dict:
    """Tehdit kaydının OYUNCUYA giden hali.

    Grubun kendi gürültüsünü, bölgenin dikkatini ve son karşılaşmayı görmesi
    oyunun kendisidir — "dikkatli seyahat et" ancak ölçülebilirse bir karardır.
    Ama YOĞUNLUK bir bilgidir: yalnız KEŞFEDİLMİŞ yerlerin ölü yoğunluğu
    gönderilir. Gidilmemiş bir yerin ne kadar kalabalık olduğunu oyuncular
    haritaya bakarak öğrenemez.
    """
    yerler = world_map.get("places") if isinstance(world_map, dict) else {}
    yerler = yerler if isinstance(yerler, dict) else {}
    bilinen = {ad for ad, bilgi in yerler.items() if knowledge_of(bilgi) == "keşfedildi"}
    simdiki = world_map.get("current") if isinstance(world_map, dict) else None
    if simdiki:
        bilinen.add(simdiki)

    yogunluk = threat.get("density")
    yogunluk = yogunluk if isinstance(yogunluk, dict) else {}

    # Göç hareketleri: yalnız BİLİNEN yerlerin adları görünür. Grup, hiç
    # duymadığı bir bölgeden ölü çekildiğini haritaya bakarak öğrenemez.
    def _gorunur_goc(kayit):
        if not isinstance(kayit, dict):
            return None
        kaynaklar = [k for k in (kayit.get("from") or [])
                     if isinstance(k, dict) and k.get("place") in bilinen]
        if kayit.get("target") not in bilinen and not kaynaklar:
            return None
        return {"target": kayit.get("target") if kayit.get("target") in bilinen else "?",
                "gain": kayit.get("gain"), "from": kaynaklar,
                "type": kayit.get("type")}

    gocler = [g for g in (_gorunur_goc(k) for k in (threat.get("migrations") or [])[-4:]) if g]

    return {
        "noise": threat.get("noise", 0),
        "heat": threat.get("heat", 0),
        "quiet_turns": threat.get("quiet_turns", 0),
        "travelling": bool(threat.get("travelling")),
        "encounters": threat.get("encounters", 0),
        "last": threat.get("last") or {},
        "history": (threat.get("history") or [])[-5:],
        "density": {ad: round(float(deger)) for ad, deger in yogunluk.items()
                    if (ad in bilinen or ad == "yol")
                    and isinstance(deger, (int, float))},
        "migrations": gocler,
    }


# Bir seçimden BAŞKASINA gösterilecek alanlar. Geri kalanı (metin, kategori,
# zar, seçenek kimliği, harcama) tur geçilene kadar sahibine özeldir.
PICK_ACIK_ALANLAR = ("player", "ts", "timeout")


def mask_picks(round_body, viewer=None, reveal=False) -> dict:
    """Açık turda BAŞKA oyuncuların kararını gizler.

    Oyuncular birbirinin kararını tur geçmeden görmemeli: yoksa herkes son
    seçeni bekler, kararlar birbirine göre ayarlanır ve aynı anda karar verme
    gerilimi kaybolur. Kim karar VERDİĞİ görünür (tur ne zaman kapanacak
    bilinsin), NE seçtiği görünmez.

    Kararlar bir sonraki turun başında yayınlanan sahneyle birlikte zaten
    açılır — orada kimin ne yaptığı hikayenin kendisidir.

    `reveal=True`: anlatıcı ve TEK EKRAN masası her şeyi görür — masadaki tek
    cihazın kendinden bir şey saklaması anlamsız.
    """
    if not isinstance(round_body, dict):
        return round_body
    picks = round_body.get("picks")
    if reveal or not isinstance(picks, dict):
        return round_body
    gizlenmis = {}
    for name, pick in picks.items():
        if not isinstance(pick, dict):
            gizlenmis[name] = pick
            continue
        if viewer and name == viewer:
            gizlenmis[name] = pick
            continue
        kirpik = {k: v for k, v in pick.items() if k in PICK_ACIK_ALANLAR}
        kirpik["player"] = pick.get("player", name)
        # Arayüz "karar verdi ama ne olduğunu göremezsin" diyebilsin.
        kirpik["gizli"] = True
        gizlenmis[name] = kirpik
    return {**round_body, "picks": gizlenmis}


def public_round(round_state, actors=None) -> dict:
    """Turun oyunculara giden hali.

    Seçimlerin GÖVDESİ burada hâlâ tamdır; kime ne gösterileceğine `mask_picks`
    karar verir ve bunu API katmanı uygular (bkz. create_app → after_request),
    çünkü "kim bakıyor" bilgisi oturuma aittir, servise değil.
    """
    round_ = round_state if isinstance(round_state, Round) else Round.from_dict(round_state)
    now = time.time()
    body = round_.to_dict()
    body["remaining"] = round_.remaining(now)
    body["expired"] = round_.expired(now)
    body["actors"] = list(actors or [])
    body["waiting"] = round_.waiting_for(actors or [])
    body["all_picked"] = round_.all_picked(actors or [])
    body["server_ts"] = now
    return body

