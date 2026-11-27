-- ######## PART 1: KPI AirBnb ########

--## KPI 1: Evolution du prix moyen de la nuitée et nombre d'annonces par mois.
-- Type de graphique: courbe + diagramme en barres.
-- Tables: "listing_snapshots", "listings". Filtres: district et rooms.

SELECT l.district AS arrondissement,
        s.checkin_month AS mois,
        l.rooms AS nb_pieces,
        COUNT(s.price) AS nb_annonces,
        SUM(s.price) AS prix_total
    FROM listing_snapshots s
    JOIN listings l ON l.listing_id = s.listing_id
    GROUP BY l.district, s.checkin_month, l.rooms
    ORDER BY l.arrondissement, s.checkin_month, l.rooms;

--## KPI 2: Distribution du prix de la nuitée selon le type de logement (nombre de chambres).
-- Type de graphique: boîte à moustache.
-- Tables: "listings" et "listings_snapshots". Filtre: district.

SELECT l.district AS arrondissement,
        l.rooms AS nb_pieces,
        s.price
    FROM listing_snapshots s
    JOIN listings l ON l.listing_id = s.listing_id
    WHERE s.price IS NOT NULL;

--## KPI 3: Carte interactive des annonces actuelles et du prix de la nuitée.
-- Type de graphique: carte interactive.
-- Tables: "listings" et "listings_snapshots". Filtre: rooms.

SELECT l.listing_id,
        l.latitude,
        l.longitude,
        l.district AS arrondissement,
        l.rooms AS nb_rooms,
        s.price
    FROM listing_snapshots s
    JOIN listings l ON l.listing_id = s.listing_id
    WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM listing_snapshots)
    GROUP BY 1, 2, 3, 4, 5;

--## KPI 4: volumes d'annonces par arrondissement (couleur) et prix moyen (texte).
-- Type de graphique: carte interactive.
-- Tables: "listings" et "listings_snapshots". Filtre: rooms.

SELECT l.district AS arrondissement,
        l.rooms AS nb_pieces,
        COUNT(DISTINCT l.listing_id) AS nb_logements,
        ROUND(AVG(s.price), 2) AS prix_moyen
    FROM listing_snapshots s
    JOIN listings l ON l.listing_id = s.listing_id
    WHERE s.snapshot_date = (SELECT MAX(snapshot_date) FROM listing_snapshots)
    GROUP BY 1, 2;

--## KPI 5: Top 10 des équipements les plus présents dans les logements.
-- Type de graphique: diagramme en barres horizontales ordonnées.
-- Tables: "listing_amenities".

SELECT a.name AS nom,
        COUNT(*) AS nb_logements,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM listings), 1) AS pourcentage
    FROM listing_amenities la
    JOIN amenities a ON a.amenity_id = la.amenity_id
    GROUP BY a.name
    ORDER BY nb_logements DESC
    LIMIT 10;

-- ######## PART 2: KPI loyers annuels ########

--# KPI 6: Loyer de référence selon le nombre de pièces et l'époque de construction.
-- Type de graphique: histogramme groupé. 
-- Tables: "neighboroods" et "rents". Filtres: district, neighborood, meublé/non meublé.

SELECT n.district AS arrondissement,
        n.neighborhood_id AS id_quartier,
        n.neighborhood_name AS nom_quartier,
        r.rooms AS nb_pieces,
        r.construction_period AS epoque,
        r.furnished AS meuble,
        r.ref_rent AS loyer_ref,
        r.max_rent AS loyer_max,
        r.min_rent AS loyer_min
        FROM rent r
        JOIN neighborhoods n ON n.neighborhood_id = r.neighborhood_id
        WHERE r.year = 2025;

--# KPI 7: carte intercative avec le prix au m2 de référence par arrondissement.
-- Type de graphique: carte interactive.
-- Tables: "neighboroods" et "rents". Filtres: meublé/non meublé.

SELECT n.district AS arrondissement,
        n.neighborhood_id AS id_quartier,
        n.neighborhood_name AS nom_quartier,
        r.rooms AS nb_pieces,
        r.construction_period AS epoque,
        r.furnished AS meuble,
        r.ref_rent AS loyer_ref,
        r.max_rent AS loyer_max,
        r.min_rent AS loyer_min
        FROM rent r
        JOIN neighborhoods n ON n.neighborhood_id = r.neighborhood_id
        WHERE r.year = 2025;