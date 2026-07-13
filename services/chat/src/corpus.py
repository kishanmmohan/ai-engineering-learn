"""In-memory corpus for the /similar endpoint (M3).

~50 short, single-sentence documents spread across a handful of clearly separated
topics (programming languages, coffee, running shoes, travel, cooking, fitness,
home tech, gardening, phone firmware) so that a clean query has an obvious right
answer. One sentence each (~15-25 tokens) on purpose: it makes the corpus
embedding cost easy to estimate on paper (#1 tokens) before checking it against
the trace.

TRAP_PAIR points at two documents on the SAME topic with OPPOSITE sentiment
(docs 48 and 49: a firmware update that helped vs. hurt battery life, phrased
with nearly identical tokens). They exist for the M3 self-check: a query about
that topic ranks BOTH high because cosine similarity measures topical/lexical
proximity, not truth or sentiment — a high-similarity result that is the wrong
answer. See the /similar section of the README for the write-up and the fix.
"""

# Each multi-line entry is wrapped in parens (explicit grouping) so the adjacent
# string literals read as one intentional document, not a missing comma between
# two list items.
CORPUS: list[str] = [
    # --- programming languages / data (0-9) ---
    (
        "Python is the most popular language for data science thanks to pandas, "
        "NumPy, and scikit-learn."
    ),
    (
        "R remains a favorite for statisticians because of its rich modeling and "
        "plotting ecosystem."
    ),
    (
        "SQL is essential for querying and aggregating data stored in relational "
        "databases."
    ),
    (
        "Rust offers memory safety without a garbage collector, making it great for "
        "systems programming."
    ),
    "JavaScript runs in every browser and powers most interactive web front ends.",
    "Go is prized for simple concurrency and fast compilation in backend services.",
    (
        "Julia targets high-performance numerical computing with a syntax friendly to "
        "scientists."
    ),
    "TypeScript adds static types to JavaScript, catching many bugs before runtime.",
    (
        "C++ gives fine-grained control over memory and is common in games and "
        "high-frequency trading."
    ),
    (
        "Java's mature ecosystem and JVM make it a staple for large enterprise "
        "applications."
    ),
    # --- coffee (10-15) ---
    (
        "Pour-over coffee highlights bright, delicate flavors when you use a "
        "medium-fine grind."
    ),
    (
        "Espresso extracts a concentrated shot under high pressure in about 25 to 30 "
        "seconds."
    ),
    (
        "A French press produces a full-bodied cup because the metal filter lets oils "
        "through."
    ),
    (
        "Cold brew steeps coarse grounds in cold water for twelve hours for a smooth, "
        "low-acid drink."
    ),
    "Freshly roasted beans taste best within two to four weeks of the roast date.",
    (
        "Burr grinders give a consistent particle size that drip and espresso both "
        "depend on."
    ),
    # --- running shoes (16-20) ---
    "Cushioned running shoes absorb impact and suit high-mileage road training.",
    "Racing flats are lightweight and stiff to help you turn over quickly on race day.",
    (
        "Trail running shoes add aggressive lugs and rock plates for grip on technical "
        "terrain."
    ),
    "A proper running shoe should leave about a thumb's width of space at the toe.",
    "Rotating between two pairs of running shoes can extend the life of each midsole.",
    # --- travel / cities (21-26) ---
    (
        "Tokyo blends dense neighborhoods, efficient trains, and world-class food into "
        "one city."
    ),
    "Reykjavik is a compact base for chasing the northern lights in winter.",
    "Lisbon's hills and tram lines reward travelers who don't mind a steep walk.",
    "Singapore stays hot and humid year-round, with frequent afternoon thunderstorms.",
    "Marrakech's medina is a maze of souks best explored slowly on foot.",
    "Vancouver sits between mountains and ocean, with mild but rainy winters.",
    # --- cooking (27-31) ---
    "Searing meat in a hot pan builds flavor through the Maillard reaction.",
    (
        "Resting a roast lets its juices redistribute so they don't spill out when you "
        "slice it."
    ),
    "Salting pasta water seasons the noodles from the inside as they cook.",
    (
        "A sharp knife is safer than a dull one because it needs less force and slips "
        "less."
    ),
    (
        "Blanching vegetables briefly then shocking them in ice water keeps their "
        "color bright."
    ),
    # --- fitness (32-36) ---
    "Progressive overload, adding weight or reps over time, drives strength gains.",
    "Compound lifts like squats and deadlifts train many muscle groups at once.",
    "Rest days let muscles repair and are when most adaptation actually happens.",
    "Warming up raises muscle temperature and reduces the risk of strains.",
    "Consistent sleep matters more than any single supplement for recovery.",
    # --- home tech (37-41) ---
    (
        "A mechanical keyboard's switches can be tuned for tactile, clicky, or linear "
        "feel."
    ),
    "Solid-state drives boot and load files far faster than spinning hard disks.",
    "Two monitors can boost productivity by reducing constant window switching.",
    (
        "Regular backups are the only reliable protection against ransomware and drive "
        "failure."
    ),
    "Mesh Wi-Fi systems spread coverage across a large home with multiple nodes.",
    # --- gardening (42-45) ---
    "Tomatoes need at least six hours of direct sun to ripen well.",
    "Mulching garden beds conserves moisture and suppresses weeds.",
    "Overwatering kills more houseplants than underwatering does.",
    "Composting kitchen scraps returns nutrients to the soil over a few months.",
    # --- phone firmware (46-47) + the trap pair (48-49) ---
    (
        "Installing a phone's firmware update usually takes a few minutes and requires "
        "a charged battery."
    ),
    (
        "You can roll back a phone firmware update through recovery mode if something "
        "goes wrong."
    ),
    # TRAP_PAIR: same topic (firmware update + battery), opposite sentiment,
    # nearly identical tokens — cosine cannot tell them apart.
    (
        "After the latest firmware update my phone battery easily lasts two full days "
        "— best upgrade yet."
    ),
    (
        "After the latest firmware update my phone battery barely lasts half a day — "
        "worst upgrade yet."
    ),
]

# The two same-topic / opposite-sentiment documents, by index into CORPUS.
TRAP_PAIR: tuple[int, int] = (48, 49)
