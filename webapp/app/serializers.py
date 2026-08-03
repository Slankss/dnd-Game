"""Dış dünyaya gidecek görünümler.

Anlatıcı gerçeği (`disposition`, `notes`, `gm_notes`, dünya zarı, sırlar) ile
oyuncunun bildiği ayrı iki katmandır. Oyuncuya giden HER gövde buradan geçer;
başka hiçbir yerde world_state doğrudan serileştirilmez.
"""

import time

from app.models.person import SECRET_FIELD
from app.models.round import Round
from app.models.world import GM_ONLY_FIELDS
from app.models.worldmap import knowledge_of, public_place


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
        public["map"] = {
            **world_map,
            "places": {
                name: public_place(info)
                for name, info in places.items()
            } if isinstance(places, dict) else {},
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
    return {
        "noise": threat.get("noise", 0),
        "heat": threat.get("heat", 0),
        "quiet_turns": threat.get("quiet_turns", 0),
        "travelling": bool(threat.get("travelling")),
        "encounters": threat.get("encounters", 0),
        "last": threat.get("last") or {},
        "history": (threat.get("history") or [])[-5:],
        "density": {ad: deger for ad, deger in yogunluk.items()
                    if ad in bilinen or ad == "yol"},
    }


def public_round(round_state, actors=None) -> dict:
    """Turun oyunculara giden hali.

    Seçimler bilerek AÇIKTIR: masadaki herkes kimin karar verdiğini, hangi
    kategoriyi seçtiğini ve zarının kaç geldiğini görür — tur, herkes seçim
    yapınca kapanacağı için bu bilgi oyunun kendisidir. Gizlenen tek şey
    yoktur; anlatıcıya özel alanlar zaten bu kayıtta durmuyor.
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

