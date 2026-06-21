# ─────────────────────────────────────────────
# app/movie_images.py
# Единственное место хранения всех URL изображений.
# Все изображения: Unsplash (бесплатные, высокое качество).
# ─────────────────────────────────────────────

#
# Гибридная система выбора постеров (3 шага):
#   1. IMAGE_OVERRIDES  — ручные исправления конфликтов (5 film_id)
#   2. FILM_IMAGES      — visual keyword, Group 1 (55 film_id)
#   3. GENRE formula    — GENRE_IMAGES[genre][film_id % N] для остальных
#
# routes.py передаёт только film_id — жанр берётся из FILM_GENRE.
# film_id > 100 или неизвестный жанр → DEFAULT_IMAGE
# ─────────────────────────────────────────────


# ── Группа 1: 55 фильмов с visual keyword ─────────────────────────
# Ключ   = film_id (int из MySQL)
# Значение = URL Unsplash, подобранный по visual keyword из названия
# Пометка (new) = заменён сломанный HTTP 404
FILM_IMAGES = {
      1: "https://images.unsplash.com/photo-1565793141104-0ef675e5162d?auto=format&fit=crop&w=1600&q=100",  # ACADEMY DINOSAUR [Action] — DINOSAUR (T-rex skeleton)
      3: "https://images.unsplash.com/photo-1761925531821-52e638fc849c?auto=format&fit=crop&w=1600&q=100",  # ADAPTATION HOLES [Documentary] — HOLES (cracked earth)
      5: "https://images.unsplash.com/photo-1755357864311-75505e88aa03?auto=format&fit=crop&w=1600&q=100",  # AFRICAN EGG [Family] — AFRICAN (gazelles savanna)
      7: "https://images.unsplash.com/photo-1761813409462-9329c23c7541?auto=format&fit=crop&w=1600&q=100",  # AIRPLANE SIERRA [Comedy] — AIRPLANE (cockpit)
      8: "https://images.unsplash.com/photo-1499699862610-16bb305407c0?auto=format&fit=crop&w=1600&q=100",  # AIRPORT POLLOCK [Horror] — AIRPORT (terminal)
      9: "https://images.unsplash.com/photo-1618325508550-951512a1e82d?auto=format&fit=crop&w=1600&q=100",  # ALABAMA DEVIL [Horror] — DEVIL (fire dark)
     11: "https://images.unsplash.com/photo-1767551427415-0d48eef38a10?auto=format&fit=crop&w=1600&q=100",  # ALAMO VIDEOTAPE [Foreign] — ALAMO (stone ruins)
     12: "https://images.unsplash.com/photo-1496088285923-2bcbf1ba3f62?auto=format&fit=crop&w=1600&q=100",  # ALASKA PHANTOM [Music] — ALASKA (aurora mountains)
     15: "https://images.unsplash.com/photo-1766329710745-21f110fa2d62?auto=format&fit=crop&w=1600&q=100",  # ALIEN CENTER [Foreign] — ALIEN (nebula space)
     16: "https://images.unsplash.com/photo-1754237266906-81139f60f235?auto=format&fit=crop&w=1600&q=100",  # ALLEY EVOLUTION [Foreign] — ALLEY (urban night)
     17: "https://images.unsplash.com/photo-1520206444322-d2df0dd4e78e?auto=format&fit=crop&w=1600&q=100",  # ALONE TRIP [Music] — TRIP (empty road)
     19: "https://images.unsplash.com/photo-1764158302110-404dcb1d8008?auto=format&fit=crop&w=1600&q=100",  # AMADEUS HOLY [Action] — AMADEUS (pianist grand piano)
     20: "https://images.unsplash.com/photo-1764239650973-70cb2eb66a5b?auto=format&fit=crop&w=1600&q=100",  # AMELIE HELLFIGHTERS [Music] — HELLFIGHTERS (fire sky)
     21: "https://images.unsplash.com/photo-1741781362911-7d38eab1f238?auto=format&fit=crop&w=1600&q=100",  # AMERICAN CIRCUS [Action] — CIRCUS (tent flag)
     23: "https://images.unsplash.com/photo-1677293396528-ed2a4119575d?auto=format&fit=crop&w=1600&q=100",  # ANACONDA CONFESSIONS [Animation] — ANACONDA (python)
     25: "https://images.unsplash.com/photo-1587930610005-cc8d7345170f?auto=format&fit=crop&w=1600&q=100",  # ANGELS LIFE [New] — ANGELS (angel statue Rome)
     29: "https://images.unsplash.com/photo-1769489023745-5d4effc83b9e?auto=format&fit=crop&w=1600&q=100",  # ANTITRUST TOMATOES [Action] — TOMATOES (red ripe)
     30: "https://images.unsplash.com/photo-1741850820063-4426abddb0d3?auto=format&fit=crop&w=1600&q=100",  # ANYTHING SAVANNAH [Horror] — SAVANNAH (lonely tree)
     32: "https://images.unsplash.com/photo-1546450077-c188684eb666?auto=format&fit=crop&w=1600&q=100",  # APOCALYPSE FLAMINGOS [New] — FLAMINGOS (pink flock)
     33: "https://images.unsplash.com/photo-1614729939124-032f0b56c9ce?auto=format&fit=crop&w=1600&q=100",  # APOLLO TEEN [Drama] — APOLLO (earth lunar surface)
     34: "https://images.unsplash.com/photo-1745437980540-b234c90a6557?auto=format&fit=crop&w=1600&q=100",  # ARABIA DOGMA [Horror] — ARABIA (golden sand dunes)
     35: "https://images.unsplash.com/photo-1568485298717-9de1b963697c?auto=format&fit=crop&w=1600&q=100",  # ARACHNOPHOBIA ROLLERCOASTER [Horror] — ROLLERCOASTER
     37: "https://images.unsplash.com/photo-1666036891960-93af3efb6d14?auto=format&fit=crop&w=1600&q=100",  # ARIZONA BANG [Classics] — ARIZONA (red rock canyon)
     38: "https://images.unsplash.com/photo-1637169252048-fce0129d55ee?auto=format&fit=crop&w=1600&q=100",  # ARK RIDGEMONT [Action] — ARK (Noah's Ark Kentucky)
     39: "https://images.unsplash.com/photo-1736806222682-a0c45ae44820?auto=format&fit=crop&w=1600&q=100",  # ARMAGEDDON LOST [Sci-Fi] — ARMAGEDDON (fire sky)
     40: "https://images.unsplash.com/photo-1630161861115-02123f0837e5?auto=format&fit=crop&w=1600&q=100",  # ARMY FLINTSTONES [Documentary] — ARMY (soldiers tank)
     42: "https://images.unsplash.com/photo-1758522274454-07a58f332320?auto=format&fit=crop&w=1600&q=100",  # ARTIST COLDBLOODED [Sports] — ARTIST (mixing paints)
     43: "https://images.unsplash.com/photo-1519676241691-fe10cb097ae5?auto=format&fit=crop&w=1600&q=100",  # ATLANTIS CAUSE [Family] — ATLANTIS (underwater blue)
     46: "https://images.unsplash.com/photo-1630002682400-9b8df94c2624?auto=format&fit=crop&w=1600&q=100",  # AUTUMN CROW [Games] — CROW (black crow close-up)
     47: "https://images.unsplash.com/photo-1510588960070-8e3ebf81324c?auto=format&fit=crop&w=1600&q=100",  # BABY HALL [Foreign] — BABY (sleeping newborn)
     49: "https://images.unsplash.com/photo-1552339931-988dab5c388d?auto=format&fit=crop&w=1600&q=100",  # BADMAN DAWN [Sci-Fi] — DAWN (golden hour sky)
     50: "https://images.unsplash.com/photo-1738580426685-f8f0d34291dc?auto=format&fit=crop&w=1600&q=100",  # BAKED CLEOPATRA [Family] — CLEOPATRA (sphinx pyramids)
     51: "https://images.unsplash.com/photo-1604156789095-3348604c0f43?auto=format&fit=crop&w=1600&q=100",  # BALLOON HOMEWARD [Music] — BALLOON (hot air balloons)
     52: "https://images.unsplash.com/photo-1687087172783-3a9f16246579?auto=format&fit=crop&w=1600&q=100",  # BALLROOM MOCKINGBIRD [Foreign] — BALLROOM (chandelier)
     54: "https://images.unsplash.com/photo-1432639020363-5632f7f04e0b?auto=format&fit=crop&w=1600&q=100",  # BANGER PINOCCHIO [Music] — PINOCCHIO (marionette)
     55: "https://images.unsplash.com/photo-1566747352719-cf582095b983?auto=format&fit=crop&w=1600&q=100",  # BARBARELLA STREETCAR [Sci-Fi] — STREETCAR (SF tram)
     58: "https://images.unsplash.com/photo-1771690633743-c986ceb51acf?auto=format&fit=crop&w=1600&q=100",  # BEACH HEARTBREAKERS [Documentary] — BEACH (ocean waves)
     59: "https://images.unsplash.com/photo-1754534139511-14d8d83e251f?auto=format&fit=crop&w=1600&q=100",  # BEAR GRACELAND [Children] — BEAR (grizzly wildlife)
     60: "https://images.unsplash.com/photo-1735220033809-4d4844d72d04?auto=format&fit=crop&w=1600&q=100",  # BEAST HUNCHBACK [Classics] — BEAST (wolf dark forest)
     64: "https://images.unsplash.com/photo-1507334608139-c6cbaabf6621?auto=format&fit=crop&w=1600&q=100",  # BEETHOVEN EXORCIST [Drama] — BEETHOVEN (grand piano)
     67: "https://images.unsplash.com/photo-1720081255090-d02a8165ccfe?auto=format&fit=crop&w=1600&q=100",  # BERETS AGENT [Action] — BERETS (soldiers guns)
     70: "https://images.unsplash.com/photo-1756572798557-1d196dcf8b2b?auto=format&fit=crop&w=1600&q=100",  # BIKINI BORROWERS [Animation] — BIKINI (tropical beach)
     74: "https://images.unsplash.com/photo-1654482278655-9551d4e2d1fe?auto=format&fit=crop&w=1600&q=100",  # BIRCH ANTITRUST [Music] — BIRCH (white trees forest)
     75: "https://images.unsplash.com/photo-1734333689152-35d81de4f687?auto=format&fit=crop&w=1600&q=100",  # BIRD INDEPENDENCE [Travel] — BIRD (flying wings spread)
     76: "https://images.unsplash.com/photo-1546840125-ba012c71366f?auto=format&fit=crop&w=1600&q=100",  # BIRDCAGE CASPER [Music] — BIRDCAGE (white ornate)
     77: "https://images.unsplash.com/photo-1649235311515-fa46aabbee75?auto=format&fit=crop&w=1600&q=100",  # BIRDS PERDITION [New] — BIRDS (flock cloudy sky)
     79: "https://images.unsplash.com/photo-1440711085503-89d8ec455791?auto=format&fit=crop&w=1600&q=100",  # BLADE POLISH [Drama] — BLADE (steel sword ground)
     81: "https://images.unsplash.com/photo-1681679743960-c54706d8df97?auto=format&fit=crop&w=1600&q=100",  # BLINDNESS GUN [Sci-Fi] — GUN (close-up on black)
     86: "https://images.unsplash.com/photo-1578736641330-3155e606cd40?auto=format&fit=crop&w=1600&q=100",  # BOOGIE AMELIE [Music] — BOOGIE (dancing green lights)
     87: "https://images.unsplash.com/photo-1748802633639-22f99d0b3a0c?auto=format&fit=crop&w=1600&q=100",  # BOONDOCK BALLROOM [Travel] — BALLROOM (grand empty hall)
     90: "https://images.unsplash.com/photo-1637618522871-473d7305cbee?auto=format&fit=crop&w=1600&q=100",  # BOULEVARD MOB [New] — BOULEVARD (dark city night)
     93: "https://images.unsplash.com/photo-1743309411498-a0f4f4b96b65?auto=format&fit=crop&w=1600&q=100",  # BRANNIGAN SUNRISE [New] — SUNRISE (golden mountain)
     95: "https://images.unsplash.com/photo-1541329351076-600b0f9fdf28?auto=format&fit=crop&w=1600&q=100",  # BREAKFAST GOLDFINGER [New] — BREAKFAST (coffee egg)
     97: "https://images.unsplash.com/photo-1512604076142-d6ed7d145d88?auto=format&fit=crop&w=1600&q=100",  # BRIDE INTRIGUE [Action] — BRIDE (wedding dress)
    100: "https://images.unsplash.com/photo-1746445932295-0c775335f723?auto=format&fit=crop&w=1600&q=100",  # BROOKLYN DESERT [Foreign] — BROOKLYN (Manhattan bridge)
}


# ── Жанры для формулы GENRE_IMAGES (film_id → genre) ──────────────
# routes.py не передаёт genre в get_movie_image(), поэтому
# для Group 2 (шаг 3) жанр берётся отсюда.
FILM_GENRE = {
     1:"Action",   2:"Horror",      3:"Documentary", 4:"Horror",
     5:"Family",   6:"Foreign",     7:"Comedy",      8:"Horror",
     9:"Horror",  10:"Sports",     11:"Foreign",    12:"Music",
    13:"Horror",  14:"Classics",   15:"Foreign",    16:"Foreign",
    17:"Music",   18:"Animation",  19:"Action",     20:"Music",
    21:"Action",  22:"New",        23:"Animation",  24:"Horror",
    25:"New",     26:"Sci-Fi",     27:"Sports",     28:"Comedy",
    29:"Action",  30:"Horror",     31:"Family",     32:"New",
    33:"Drama",   34:"Horror",     35:"Horror",     36:"Animation",
    37:"Classics",38:"Action",     39:"Sci-Fi",     40:"Documentary",
    41:"Travel",  42:"Sports",     43:"Family",     44:"Sci-Fi",
    45:"New",     46:"Games",      47:"Foreign",    48:"Children",
    49:"Sci-Fi",  50:"Family",     51:"Music",      52:"Foreign",
    53:"Family",  54:"Music",      55:"Sci-Fi",     56:"Action",
    57:"Travel",  58:"Documentary",59:"Children",   60:"Classics",
    61:"Drama",   62:"Documentary",63:"Family",     64:"Drama",
    65:"Horror",  66:"Children",   67:"Action",     68:"Children",
    69:"Sci-Fi",  70:"Animation",  71:"Family",     72:"Documentary",
    73:"Sci-Fi",  74:"Music",      75:"Travel",     76:"Music",
    77:"New",     78:"Animation",  79:"Drama",      80:"Family",
    81:"Sci-Fi",  82:"Family",     83:"Family",     84:"Travel",
    85:"Documentary",86:"Music",   87:"Travel",     88:"Travel",
    89:"Animation",  90:"New",     91:"Classics",   92:"Horror",
    93:"New",     94:"Family",     95:"New",        96:"New",
    97:"Action",  98:"Drama",      99:"Comedy",    100:"Foreign",
}


# ── Жанровые изображения (20 URL на жанр) ─────────────────────────
# Основная таблица: жанр → список из 20 картинок.
# assign_movie_images() выбирает из этого списка без повторов в выдаче.
GENRE_IMAGES = {

    # ── Action ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] Unsplash Search API "action sport race"
    "Action": [
        "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1552674605-db5fecabfe68?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1549476464-37392f717541?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1547153760-18fc86324498?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1544919982-b61976f0ba43?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1533284133567-0da9844151ce?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1516147697747-02adcafd3fda?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1499871435582-a1d4ff236842?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1486425091969-f62210f08a26?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1609773335024-be4301497ea9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1607515433201-98f09419ef49?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1520474151999-5cb75d6a9a62?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1551759390-5c112a9ffef0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1435244837924-21c508f9db25?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1494488802316-82250d81cfcc?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1603010569009-75aa786fe558?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1603010569028-2e831ac6ec8f?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Animation ───────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "animation colorful digital art"
    "Animation": [
        "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1543848089-530aad06491a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1636955779321-819753cd1741?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1660585266731-8cb1b1162d70?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1614854262318-831574f15f1f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1676068368612-1c8b3e2afed0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1636150721221-b88b3c2299be?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1764601842139-635f318905c6?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1773983273448-bd5b296cd530?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1636955890525-84c5fa482c85?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1738168505805-d3b28ad94f61?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1684610525931-d08fd63577ad?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1763931504206-e06cfe3cda08?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1590030398587-322cc5cf5403?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1771012610711-faf81bfd6793?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1713188090500-a4fb0d2cf309?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1769122489600-966b3d1ee38d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1774187251898-ed4f6a9e1d6c?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Children ────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "children kids playing happy"
    "Children": [
        "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1511895426328-dc8714191300?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1542281286-9e0a16bb7366?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1546410531-bb4caa6b424d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1536640712-4d4c36ff0e4e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1502086223501-7ea6ecd79368?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1533222481259-ce20eda1e20b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1627764940620-90393d0e8c34?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1533222535026-754c501569dd?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1502781252888-9143ba7f074e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1469406396016-013bfae5d83e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1516240562813-7d658edb7239?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1631194758628-71ec7c35137e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1597075958693-75173d1c837f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571593992702-27f222d4059a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1612542795178-ef13feed5ddd?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Classics ────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "vintage cinema film classic"
    "Classics": [
        "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1518929458119-e5bf444c30f4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1524985069026-dd778a71c7b4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1626814026160-2237a95fc5a0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571847140471-1d7766e825ea?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1542204165-65bf26472b9b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1568876694728-451bbf694b83?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1589569334232-fdc917c38226?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1777639629538-b96a43f6690d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1676941701414-5445e0ff1674?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1762979772530-81c3a60f5010?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1767024990882-830795cb1653?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1770902895934-b04a10daa893?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1762235634044-ac18d682a0d7?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1497942304796-b8bc2cc898f3?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Comedy ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "friends laughing comedy fun"
    "Comedy": [
        "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1491438590914-bc09fcaaf77a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1543269865-cbf427effbad?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1496337589254-7e19d01cec44?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1504196606672-aef5c9cefc92?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1506869640319-fe1a24fd76dc?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1681641095463-b4d3693a0ee3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1511988617509-a57c8a288659?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1536010305525-f7aa0834e2c7?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1504022462188-88f023db97bf?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1597736960442-d613cca349db?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1589483232748-515c025575bc?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1701858986056-c740b7309e89?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1596815139884-ff0966bb36b3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1555817129-2fa6b81bd8e5?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1681641092941-b1acee507ee0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1758525862263-af89b090fb56?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1626541702519-eb944c653d58?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Documentary ─────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "documentary camera journalism"
    "Documentary": [
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1476514525405-8edd5ea2de6c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1518020382113-a7e8fc38eac9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1556656793-08538906a9f8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1508193638397-1c4234db14d8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580707221190-bd94d9087b7f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1497015289639-54688650d173?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1493804714600-6edb1cd93080?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1596801129861-8592c97db6ad?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1543242594-c8bae8b9e708?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1569016832321-084c128adeb8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1625690303837-654c9666d2d0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1512025316832-8658f04f8a83?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1594394489098-74ac04c0fc2e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1598784124046-64dc7e92357d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1711439858551-c96a3c310075?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1485846147915-69f12fbd03b9?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Drama ───────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "theater drama stage emotional"
    "Drama": [
        "https://images.unsplash.com/photo-1576724196706-3f23f51ea351?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1514306191717-452ec28c7814?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1560719887-fe3105fa1e55?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1583482183620-f692113aafc3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1638803040283-7a5ffd48dad5?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1562329265-95a6d7a83440?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1630050525402-06c617847d27?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1615414015111-8d98cb65677e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1558970439-add78fc68990?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1588928781379-c355ab3edc9b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1603647284638-60268b672f55?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1549497538-303791108f95?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571173069043-82a7a13cee9f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1565798846807-2af22c843402?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1698678302429-3a63d3d90652?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1513614804160-44b4560c8acf?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1740867650660-e1a0a677e666?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1545129139-1beb780cf337?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1765891551971-1d12acfb0539?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Family ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "family together home warm"
    "Family": [
        "https://images.unsplash.com/photo-1767475983646-b5c392278771?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1768889828432-66e66768d53d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1528360983277-13d401cdc186?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1772311284716-cc34391d0520?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1780234492017-20971206986c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1624448445915-97154f5e688c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1637942189194-be88fb56bc32?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1654613698316-b9bce9f4b6bb?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1740679953679-23433eaf3156?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1637942189191-fa7add81c1bb?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1637942189130-729c4c3163af?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1549227082-0ea18ce30397?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1740679954227-a0cd19c042a6?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1606983773367-8f93e7bbad8d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1764006195843-e6f9a5781500?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1770871821382-60ea99b0a941?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1663229049306-33b5cd9c2134?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Foreign ─────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "world culture international foreign"
    "Foreign": [
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1523131328515-865dbf27fe0f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1685262867156-171be0d40f60?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1677663637429-2a80f1db6611?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1683606095922-cda452e83878?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1523980145253-50327d891e0e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1623676632925-bff8c60b4dc8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1621977717126-e29965156a27?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1668120084348-efc2ba0ad31d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1600633349333-eebb43d01e23?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1744181526018-f51e1a9c5423?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1679694576356-6806f425c6ad?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1773339812476-b605203799bd?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1771251004016-d879327b33c2?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1776625722848-684a176581d5?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1774109508624-b6fc1c1c7909?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1777906214653-ef5612193dee?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1775916656664-adfdf6faf0e4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1761064014209-6ee04380d0a7?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Games ───────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "gaming esports controller"
    "Games": [
        "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1493711662062-fa541adb3fc8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1598550476439-6847785fcea6?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1585620385456-4759f9b5c7d9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1563453392212-326f5e854473?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580234811497-9df7fd2f357e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580327344181-c1163234e5a0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580327332925-a10e6cb11baa?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1691359006593-3481cc87c36a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580234831315-438a4813685c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1580234797602-22c37b2a6230?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1635372730136-06b29022281c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1635372708431-64774de60e20?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1558008258-ec20a83db196?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1558008412-f42c059a9d02?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1767476907114-d7bc77571914?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1777971477431-af52e769612e?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Horror ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "horror dark scary abandoned"
    "Horror": [
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1532936991818-d0611467fbee?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1508165821229-7be282c31b6e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1481018085669-2bc6e4f00eed?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1509248961158-e54f6934749c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1504701954957-2010ec3bcec1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1560807707-8cc77767d783?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1526547462705-121430d02c2c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1543811303-5f6310068938?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1517405030045-45f7ad942106?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1516552335949-d1e27f71ca8a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1500398925958-b224455d0828?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1599509671551-6879ee499198?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1525015471056-0f7e78652361?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1598287263720-412c39bd14a9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1484608577325-c7540cc6794d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1523804427826-322aa3cfaa42?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1572283046480-e990be92d301?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1637150784649-23b893a31dd7?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Music ───────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "concert music festival band"
    "Music": [
        "https://images.unsplash.com/photo-1514320291840-2e0a9bf2a9ae?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1493225457126-a3a964f2fc49?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1470229722913-7832f30af21e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1501386761520-ef1f90c46b4f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1508854710579-5cecc3a9ff17?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1415201364774-f6f0bb35f28f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1486427944299-d1955d23e34d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1524368535928-5b5e00ddc76b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1497911270199-1c552ee64aa4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1603190287605-e6ade32fa852?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1454908027598-28c44b1716c1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1563841930606-67e2bce48b78?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1565035010268-a3816f98589a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1619229666372-3c26c399a4cb?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── New ─────────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "neon city night modern futuristic"
    "New": [
        "https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1588007375246-3ee823ef4851?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1598449935381-54511437c927?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1599060052009-24d6d0b0161c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1759701059272-d83175fff799?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1768141742644-67c2be7e741a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1775285180218-b22491f81d8f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1557672172-298e090bd0f1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1601042879364-f3947d3f9c16?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1535391879778-3bae11d29a24?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1573767291321-c0af2eaf5266?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1672872476232-da16b45c9001?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1561344640-2453889cde5b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1624075250557-9e020cecaaf6?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1557515126-1bf9ada5cb93?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1530919424169-4b95f917e937?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1545158828-4e222fdb1d5a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1548317202-26d94742e8d8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1542416409-400da26855b5?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Sci-Fi ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "space science fiction technology"
    "Sci-Fi": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1582719471384-894fbb16e074?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1446941611757-91d2c3bd3d45?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1581822261290-991b38693d1b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1687985826611-80b714011d0b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1592561199818-6b69d3d1d6e2?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1702499903230-867455db1752?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1654280983312-110b5b422397?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1639262498805-17c7dc422d37?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1688407832489-cc9db90773f5?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1681924101087-922416cba14e?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1649256308437-e93443143e3a?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1698327615546-7f30183aa4e3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1703994643772-8bbbd8590c4c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1688413399498-e35ed74b554f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1597635201981-308a4bfd0e55?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Sports ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "athlete sport competition stadium"
    "Sports": [
        "https://images.unsplash.com/photo-1530549387789-4c1017266635?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1560090995-01632a28895b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1560089000-7433a4ebbd64?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1541625390725-39ec9fecaf17?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1517649763962-0c623066013b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571731956672-f2b94d7dd0cb?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1575361204480-aadea25e6e68?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1530138948699-6a75eebc9d9b?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1565483276060-e6730c0cc6a1?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1663852914605-f5d7f50e7392?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1564833592193-3270b5618e7f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1623711146316-e94fa5c239d9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1762013315117-1c8005ad2b41?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1598121876853-82437626c783?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1608154119029-53f3c6ad12e4?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1755877956621-5fac2eae4ebb?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1612023676043-5c26a8088b4d?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1544366981-43d8d59eeba9?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1709133636649-7cb8959ddcb3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1764050359179-517599dab87b?auto=format&fit=crop&w=1600&q=100",
    ],

    # ── Travel ──────────────────────────────────────────────────────
    # [0-7] проверены ранее | [8-19] "travel adventure landscape explore"
    "Travel": [
        "https://images.unsplash.com/photo-1583244685026-d8519b5e3d21?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1596003903067-bf5762ad5c19?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1439853949127-fa647821eba0?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1608953029601-7a6e5e7fd548?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1448518340475-e3c680e9b4be?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1571161535093-e7642c4bd0c8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1625472603517-1b0dc72846ab?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1628533133595-8305ecaf8620?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1682685797229-b2930538da47?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1626948688703-0136bc0a90da?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1445363692815-ebcd599f7621?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1548166752-a7767d3385c8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1573197441318-dd67c7e2eea3?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1673505413397-0cd0dc4f5854?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1493689102740-d55bd3d0e3c8?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1588676509970-63fe490c3712?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1512439635661-28312317724f?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1716138466846-df5a4bba24ef?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1716138467030-6e157b99ab0c?auto=format&fit=crop&w=1600&q=100",
        "https://images.unsplash.com/photo-1716138468010-0cd7d1a43fb3?auto=format&fit=crop&w=1600&q=100",
    ],

}


# ── Ручные исправления конфликтов (IMAGE_OVERRIDES) ───────────────
# Для 5 film_id формула film_id % N давала одинаковый индекс.
# Здесь им вручную назначены другие URL того же жанра (HTTP 200).
# Шаг 1 в get_movie_image() — проверяется первым.
IMAGE_OVERRIDES = {
    24: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1600&q=100",  # Horror[0]  — ANALYZE HOOSIERS
    68: "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?auto=format&fit=crop&w=1600&q=100",  # Children[0]— BETRAYED REAR
    71: "https://images.unsplash.com/photo-1768889828432-66e66768d53d?auto=format&fit=crop&w=1600&q=100",  # Family[1]  — BILKO ANONYMOUS
    78: "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1600&q=100",  # Animation[0]—BLACKOUT PRIVATE
    83: "https://images.unsplash.com/photo-1772311284716-cc34391d0520?auto=format&fit=crop&w=1600&q=100",  # Family[5]  — BLUES INSTINCT
}


# ── Заглушка ──────────────────────────────────────────────────────
# Показывается если film_id нет ни в одном словаре и жанр неизвестен.
# Также используется в index.html через onerror как fallback.
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=1600&q=100"


def get_movie_image(film_id, genre=None):
    """
    Возвращает URL постера для фильма. Три шага:

    1. IMAGE_OVERRIDES  — ручные исправления конфликтов (5 film_id)
    2. FILM_IMAGES      — visual keyword фильмы, Group 1 (55 film_id)
    3. GENRE formula    — GENRE_IMAGES[genre][film_id % N]

    Аргументы:
      film_id — int, первичный ключ фильма из MySQL
      genre   — str или None (routes.py не передаёт, берём из FILM_GENRE)
    """
    # Шаг 1: ручное исправление конфликтов
    if film_id in IMAGE_OVERRIDES:
        return IMAGE_OVERRIDES[film_id]

    # Шаг 2: visual keyword фильм (Group 1)
    if film_id in FILM_IMAGES:
        return FILM_IMAGES[film_id]

    # Шаг 3: жанровая формула для Group 2
    resolved_genre = genre or FILM_GENRE.get(film_id)
    images = GENRE_IMAGES.get(resolved_genre, [DEFAULT_IMAGE])
    n = len(images)
    return images[film_id % n]


# for genre, images in GENRE_IMAGES.items():
#     print(genre, len(images), len(set(images)))
