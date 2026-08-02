"""Dış dünyaya gidecek görünümler.

Anlatıcı gerçeği (`disposition`, `notes`, `gm_notes`, dünya zarı, sırlar) ile
oyuncunun bildiği ayrı iki katmandır. Oyuncuya giden HER gövde buradan geçer;
başka hiçbir yerde world_state doğrudan serileştirilmez.
"""

from app.models.person import SECRET_FIELD
from app.models.world import GM_ONLY_FIELDS


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

