import { useState, useEffect } from 'react'
import { useApi } from '../api.js'

// ── Network definitions ────────────────────────────────────────────────────
const PARIS_NETWORK = [
  // Métro (5 plus fréquentés)
  { name: 'M1',     type: 'Métro',   color: '#FFCE00', text: '#000', freq_peak: 2,  freq_off: 4,   dirA: 'La Défense',          dirB: 'Château de Vincennes' },
  { name: 'M4',     type: 'Métro',   color: '#9B1B80', text: '#fff', freq_peak: 3,  freq_off: 5,   dirA: 'Montrouge',           dirB: 'Clignancourt' },
  { name: 'M6',     type: 'Métro',   color: '#82BE00', text: '#000', freq_peak: 4,  freq_off: 6,   dirA: 'Charles de Gaulle',   dirB: 'Nation' },
  { name: 'M13',    type: 'Métro',   color: '#4DB848', text: '#fff', freq_peak: 4,  freq_off: 6,   dirA: 'Châtillon-Montrouge', dirB: 'Asnières-Gennevilliers' },
  { name: 'M14',    type: 'Métro',   color: '#6B267E', text: '#fff', freq_peak: 2,  freq_off: 3,   dirA: 'Olympiades',          dirB: 'Saint-Lazare' },
  // RER
  { name: 'RER A',  type: 'RER',     color: '#FF1400', text: '#fff', freq_peak: 5,  freq_off: 10,  dirA: 'Cergy / Poissy',      dirB: 'Marne-la-Vallée / Boissy' },
  { name: 'RER B',  type: 'RER',     color: '#3C91DC', text: '#fff', freq_peak: 5,  freq_off: 10,  dirA: 'Robinson / St-Rémy',  dirB: 'Roissy CDG / Mitry' },
  { name: 'RER C',  type: 'RER',     color: '#FECE00', text: '#000', freq_peak: 10, freq_off: 15,  dirA: 'Versailles',          dirB: 'Juvisy / Brétigny' },
  { name: 'RER D',  type: 'RER',     color: '#00814F', text: '#fff', freq_peak: 8,  freq_off: 12,  dirA: 'Orry-la-Ville',       dirB: 'Corbeil / Melun' },
  { name: 'RER E',  type: 'RER',     color: '#C04191', text: '#fff', freq_peak: 12, freq_off: 20,  dirA: 'Haussmann-St-Lazare', dirB: 'Chelles / Tournan' },
  // Tramway
  { name: 'T3a',    type: 'Tramway', color: '#6E3219', text: '#fff', freq_peak: 6,  freq_off: 8,   dirA: 'Pont du Garigliano',  dirB: 'Porte de Vincennes' },
  { name: 'T3b',    type: 'Tramway', color: '#6E3219', text: '#fff', freq_peak: 8,  freq_off: 12,  dirA: 'Porte de Vincennes',  dirB: 'Porte de la Chapelle' },
  // Bus
  { name: 'Bus 38', type: 'Bus',     color: '#F5A623', text: '#000', freq_peak: 6,  freq_off: 9,   dirA: 'Gare du Nord',        dirB: 'Clamart' },
  { name: 'Bus 63', type: 'Bus',     color: '#F5A623', text: '#000', freq_peak: 8,  freq_off: 12,  dirA: 'Tour Eiffel',         dirB: 'Gare de Lyon' },
  { name: 'Bus 95', type: 'Bus',     color: '#F5A623', text: '#000', freq_peak: 7,  freq_off: 10,  dirA: 'Montrouge',           dirB: 'Pont de Levallois' },
]

const LILLE_NETWORK = [
  { name: 'M1',       type: 'Métro',   color: '#FF6600', text: '#fff', freq_peak: 3,  freq_off: 5,   dirA: 'CHR-B-Calmette',    dirB: 'Lomme-Canteleu' },
  { name: 'M2',       type: 'Métro',   color: '#0099CC', text: '#fff', freq_peak: 4,  freq_off: 6,   dirA: 'Saint-Philibert',   dirB: 'CH Dron Tourcoing' },
  { name: 'Tram R',   type: 'Tramway', color: '#8B4513', text: '#fff', freq_peak: 10, freq_off: 15,  dirA: 'Tourcoing Centre',  dirB: 'Lille Gare Flandres' },
  { name: 'L1',       type: 'Bus',     color: '#00A651', text: '#fff', freq_peak: 5,  freq_off: 8,   dirA: 'Quatre Cantons',    dirB: 'CHR B-Calmette' },
  { name: 'L3',       type: 'Bus',     color: '#0072BC', text: '#fff', freq_peak: 7,  freq_off: 10,  dirA: 'Bois-Blancs',       dirB: 'Cité Scientifique' },
  { name: 'L5',       type: 'Bus',     color: '#EE1C25', text: '#fff', freq_peak: 6,  freq_off: 9,   dirA: 'Faches-Thumesnil',  dirB: 'Croix-Centre' },
  { name: 'Eurostar', type: 'Train',   color: '#1B1464', text: '#FFD700', freq_peak: 60, freq_off: 120, dirA: 'London St Pancras', dirB: 'Paris Gare du Nord' },
]

const TYPE_ORDER = ['Métro', 'RER', 'Tramway', 'Bus', 'Train']
const TYPE_ICON  = { Métro: '🚇', RER: '🚊', Tramway: '🚋', Bus: '🚌', Train: '🚄' }
const STATUS_COL = { NORMAL: '#22c55e', REDUCED: '#f59e0b', DISRUPTED: '#ef4444' }

// ── Station data ───────────────────────────────────────────────────────────
const STATION_DATA = {
  Paris: {
    'M1':     ['La Défense – Grande Arche', 'Esplanade de la Défense', 'Pont de Neuilly', 'Les Sablons', 'Porte Maillot', 'Argentine', 'Ch. de Gaulle-Étoile', 'George V', 'Franklin D. Roosevelt', 'Champs-Élysées–Clemenceau', 'Concorde', 'Tuileries', 'Palais Royal – Louvre', 'Châtelet', 'Hôtel de Ville', 'Saint-Paul', 'Bastille', 'Gare de Lyon', 'Reuilly-Diderot', 'Montgallet', 'Daumesnil', 'Nation', 'Porte de Vincennes', 'Saint-Mandé', 'Vincennes'],
    'M4':     ['Montrouge', 'Bagneux – Lucie Aubrac', 'Mairie de Montrouge', 'Alésia', 'Mouton-Duvernet', 'Denfert-Rochereau', 'Raspail', 'Montparnasse-Bienvenüe', 'Vavin', 'Notre-Dame-des-Champs', 'Saint-Placide', 'Saint-Sulpice', 'Saint-Germain-des-Prés', 'Odéon', 'Cité', 'Châtelet', 'Les Halles', 'Étienne Marcel', 'Réaumur-Sébastopol', 'Strasbourg-Saint-Denis', "Gare de l'Est", 'Château-Landon', 'Gare du Nord', 'Marcadet-Poissonniers', 'Simplon', 'Porte de Clignancourt'],
    'M6':     ["Ch. de Gaulle-Étoile", 'Kléber', 'Boissière', 'Trocadéro', 'Passy', 'Bir-Hakeim', 'Dupleix', 'La Motte-Picquet-Grenelle', 'Commerce', 'Félix Faure', 'Boucicaut', 'Lourmel', 'Balard', 'Corentin Celton', 'Issy-Val de Seine', 'Clamart', 'Châtillon-Montrouge'],
    'M13':    ['Châtillon-Montrouge', 'Malakoff – Plateau de Vanves', 'Malakoff – Rue Étienne Dolet', 'Montrouge', 'Alésia', 'Plaisance', 'Pernety', 'Montparnasse-Bienvenüe', 'Duroc', 'Saint-François-Xavier', 'Varenne', 'Invalides', 'Champs-Élysées–Clemenceau', 'Miromesnil', 'Saint-Lazare', 'Liège', 'Place de Clichy', 'Brochant', 'Porte de Clichy', 'Gabriel Péri', 'Asnières-Gennevilliers'],
    'M14':    ['Olympiades', 'Bibliothèque François Mitterrand', 'Cour Saint-Émilion', 'Bercy', 'Gare de Lyon', 'Châtelet', 'Pyramides', 'Madeleine', 'Saint-Lazare', 'Pont Cardinet', 'Porte de Clichy', 'Mairie de Saint-Ouen'],
    'RER A':  ['Cergy-le-Haut / Poissy', 'Cergy-Préfecture', 'Nanterre-Université', 'La Défense', "Ch. de Gaulle-Étoile", 'Auber', 'Châtelet-Les-Halles', 'Gare de Lyon', 'Nation', 'Vincennes', 'Val de Fontenay', 'Torcy', 'Marne-la-Vallée – Chessy'],
    'RER B':  ["Saint-Rémy-lès-Chevreuse", 'Gif-sur-Yvette', 'Massy-Palaiseau', 'Antony', 'Bourg-la-Reine', 'Denfert-Rochereau', 'Châtelet-Les-Halles', 'Gare du Nord', 'La Plaine-Stade de France', "Aulnay-sous-Bois", 'Aéroport CDG 1', 'Aéroport CDG 2 / Mitry'],
    'RER C':  ["Versailles-Château", 'Versailles-Chantiers', 'Viroflay-Rive-Gauche', 'Javel', "Musée d'Orsay", 'Saint-Michel-Notre-Dame', 'Austerlitz', 'Bibliothèque F. Mitterrand', "Ivry-sur-Seine", 'Juvisy', 'Brétigny'],
    'RER D':  ["Orry-la-Ville-Coye", 'Creil', 'Gare du Nord', 'Châtelet-Les-Halles', 'Gare de Lyon', "Villeneuve-Saint-Georges", 'Corbeil-Essonnes / Melun'],
    'RER E':  ['Haussmann-Saint-Lazare', 'Magenta', 'Gare du Nord', 'Pantin', 'Bondy', 'Chelles-Gournay', 'Tournan'],
    'T3a':    ["Pont du Garigliano", 'Balard', 'Lourmel', 'Boucicaut', 'Brancion', "Porte de Vanves", 'Didot', "Porte d'Orléans", 'Cité Universitaire', 'Glacière-Tolbiac', "Porte d'Italie", "Porte de Choisy", "Porte d'Ivry", 'Bibliothèque F. Mitterrand', 'Porte de Vincennes'],
    'T3b':    ['Porte de Vincennes', 'Porte de Montreuil', 'Porte de Bagnolet', 'Porte de Lilas', 'Pré-Saint-Gervais', 'Porte de Pantin', 'Ella Fitzgerald', 'Proudhon-Gardinoux', 'Porte de la Chapelle'],
    'Bus 38': ["Gare du Nord", "Gare de l'Est", 'République', 'Châtelet', 'Saint-Michel', 'Port-Royal', 'Denfert-Rochereau', 'Alésia', 'Mouton-Duvernet', 'Clamart'],
    'Bus 63': ['Tour Eiffel', 'Trocadéro', 'Iéna', 'Victor Hugo', 'Ranelagh', 'Saint-Cloud', "Gare d'Austerlitz", 'Gare de Lyon'],
    'Bus 95': ['Montrouge', 'Denfert-Rochereau', 'Port-Royal', 'Saint-Germain-des-Prés', 'Opéra', 'Place de Clichy', 'Guy Môquet', 'Pont de Levallois'],
  },
  Lille: {
    'M1':       ['CHR B-Calmette', 'Eurasanté', 'CHRU-C.O. Lambret', 'Caulier', 'Wazemmes', 'Gambetta', 'République-Beaux-Arts', 'Rihour', 'Gare Lille-Flandres', 'Gare Lille-Europe', 'Romarin', 'Roubaix-Grand Place', 'Roubaix-Eurotéléport', 'Lomme-Canteleu'],
    'M2':       ['Saint-Philibert', 'Mons-en-Barœul', 'Moulins', 'Mairie de Mons', 'Hôtel de Ville V.d\'Ascq', 'Pont de Bois', '4 Cantons – Stade P.M.', 'Croix-Hem', 'Croix-Centre', 'Roubaix-Centre', 'Tourcoing-Sébastopol', 'Tourcoing-Centre', 'CH Dron Tourcoing'],
    'Tram R':   ['Tourcoing Centre', 'Square Lagaë', 'Le Beau Regard', 'Wattrelos-Est', 'Le Fresnoy – Roubaix', 'Hôtel de Ville Roubaix', 'Grand Place Roubaix', 'Eurotéléport', 'Roubaix Europe', 'Vieil Hem', 'Lille-Gare Flandres'],
    'L1':       ["Quatre Cantons", "Hôtel de Ville V.d'Ascq", 'Pont de Bois', 'Triolo', "Gare Lille-Europe", 'Gare Lille-Flandres', 'Wazemmes', 'CHR B-Calmette'],
    'L3':       ['Bois-Blancs', 'Saint-Sauveur', 'Gare Lille-Flandres', 'Rihour', 'Euralille', 'Cité Scientifique'],
    'L5':       ['Faches-Thumesnil', 'Lezennes', 'Hellemmes', 'Villeneuve d\'Ascq', 'Roubaix-Centre', 'Croix-Centre'],
    'Eurostar': ['Paris Gare du Nord', "Calais-Fréthun", 'Lille-Europe', 'Ebbsfleet International', 'London St Pancras'],
  },
}

// ── Real GPS station coordinates [lng, lat] per line ─────────────────────
const STATION_COORDS = {
  Paris: {
    // M1: La Défense → Vincennes (E-W axis, 25 stations)
    M1: [
      [2.2373,48.8920],[2.2481,48.8896],[2.2556,48.8842],[2.2675,48.8776],
      [2.2815,48.8775],[2.2893,48.8760],[2.2951,48.8738],[2.3007,48.8718],
      [2.3083,48.8684],[2.3136,48.8669],[2.3213,48.8654],[2.3310,48.8654],
      [2.3369,48.8635],[2.3470,48.8603],[2.3519,48.8574],[2.3598,48.8551],
      [2.3692,48.8531],[2.3731,48.8445],[2.3880,48.8484],[2.3955,48.8481],
      [2.3960,48.8399],[2.3959,48.8482],[2.4155,48.8465],[2.4238,48.8445],
      [2.4396,48.8448],
    ],
    // M4: Montrouge (S) → Porte de Clignancourt (N), 26 stations
    M4: [
      [2.3157,48.8129],[2.3155,48.8192],[2.3162,48.8208],[2.3249,48.8280],
      [2.3250,48.8340],[2.3326,48.8341],[2.3295,48.8405],[2.3210,48.8428],
      [2.3292,48.8432],[2.3294,48.8461],[2.3278,48.8478],[2.3318,48.8512],
      [2.3340,48.8536],[2.3411,48.8525],[2.3474,48.8554],[2.3470,48.8603],
      [2.3481,48.8623],[2.3496,48.8636],[2.3516,48.8660],[2.3536,48.8701],
      [2.3591,48.8765],[2.3614,48.8782],[2.3570,48.8806],[2.3484,48.8919],
      [2.3477,48.8956],[2.3441,48.9025],
    ],
    // M6: Ch. de Gaulle → Nation arc via 15e arr, 17 stations
    M6: [
      [2.2951,48.8738],[2.2974,48.8711],[2.3007,48.8678],[2.2923,48.8640],
      [2.2859,48.8574],[2.2920,48.8508],[2.2975,48.8481],[2.3041,48.8475],
      [2.3029,48.8455],[2.3054,48.8435],[2.3041,48.8397],[2.3031,48.8352],
      [2.2921,48.8344],[2.2810,48.8376],[2.2718,48.8245],[2.2598,48.8129],
      [2.3012,48.8150],
    ],
    // M13: Châtillon-Montrouge → Asnières-Gennevilliers, 21 stations
    M13: [
      [2.3012,48.8150],[2.3047,48.8198],[2.3047,48.8208],[2.3157,48.8230],
      [2.3249,48.8280],[2.3212,48.8345],[2.3155,48.8408],[2.3210,48.8428],
      [2.3160,48.8465],[2.3105,48.8505],[2.3146,48.8569],[2.3098,48.8625],
      [2.3136,48.8669],[2.3085,48.8728],[2.3087,48.8744],[2.3072,48.8770],
      [2.3187,48.8840],[2.3198,48.8885],[2.3130,48.8930],[2.3047,48.8973],
      [2.2930,48.9160],
    ],
    // M14: Olympiades (S) → Saint-Lazare/Mairie de Saint-Ouen (N), 12 stations
    M14: [
      [2.3647,48.8278],[2.3765,48.8380],[2.3836,48.8370],[2.3760,48.8413],
      [2.3731,48.8445],[2.3470,48.8603],[2.3320,48.8630],[2.3248,48.8706],
      [2.3245,48.8755],[2.3244,48.8826],[2.3200,48.8958],[2.3137,48.9013],
    ],
    // RER A: Cergy/Poissy (W) → Marne-la-Vallée (E), 13 key stops
    'RER A': [
      [2.0700,49.0400],[2.0779,49.0353],[2.1941,48.9048],[2.2373,48.8920],
      [2.2951,48.8738],[2.3286,48.8745],[2.3471,48.8599],[2.3731,48.8445],
      [2.3959,48.8482],[2.4397,48.8448],[2.4782,48.8479],[2.7756,48.8571],
      [2.7793,48.8432],
    ],
    // RER B: St-Rémy (S) → CDG/Mitry (N), 12 key stops
    'RER B': [
      [2.0725,48.7106],[2.1565,48.7022],[2.2578,48.7223],[2.3009,48.7543],
      [2.3047,48.7872],[2.3326,48.8341],[2.3471,48.8599],[2.3570,48.8806],
      [2.3591,48.9120],[2.5202,48.9402],[2.5500,49.0009],[2.5672,49.0037],
    ],
    // RER C: Versailles (W) → Brétigny (SE), 11 stops
    'RER C': [
      [2.1254,48.8048],[2.1234,48.8100],[2.1636,48.8082],[2.2792,48.8471],
      [2.3249,48.8609],[2.3471,48.8599],[2.3670,48.8465],[2.3765,48.8380],
      [2.3848,48.8238],[2.3770,48.6892],[2.3063,48.6157],
    ],
    // RER D: Orry-la-Ville (N) → Corbeil/Melun (S), 7 stops
    'RER D': [
      [2.5002,49.0740],[2.5263,49.0052],[2.3570,48.8806],[2.3471,48.8599],
      [2.3731,48.8445],[2.4642,48.7323],[2.4897,48.5995],
    ],
    // RER E: Haussmann (W) → Tournan (E), 7 stops
    'RER E': [
      [2.3249,48.8745],[2.3585,48.8795],[2.3570,48.8806],[2.4015,48.8985],
      [2.4804,48.8976],[2.5874,48.8773],[3.0024,48.7431],
    ],
    // T3a: Pont du Garigliano (W) → Porte de Vincennes (E), 15 stops
    T3a: [
      [2.2792,48.8471],[2.2921,48.8344],[2.3031,48.8352],[2.3041,48.8397],
      [2.3135,48.8247],[2.3200,48.8173],[2.3212,48.8137],[2.3347,48.8126],
      [2.3410,48.8246],[2.3415,48.8222],[2.3497,48.8190],[2.3643,48.8156],
      [2.3748,48.8190],[2.3765,48.8380],[2.4155,48.8465],
    ],
    // T3b: Porte de Vincennes (W) → Porte de la Chapelle (N), 9 stops
    T3b: [
      [2.4155,48.8465],[2.4199,48.8588],[2.4200,48.8636],[2.4128,48.8756],
      [2.4019,48.8821],[2.3994,48.8966],[2.3932,48.9026],[2.3857,48.9054],
      [2.3622,48.9035],
    ],
    // Bus 38: Gare du Nord → Clamart, 10 stops
    'Bus 38': [
      [2.3570,48.8806],[2.3591,48.8765],[2.3625,48.8714],[2.3471,48.8599],
      [2.3422,48.8534],[2.3369,48.8435],[2.3326,48.8341],[2.3249,48.8280],
      [2.3250,48.8340],[2.2873,48.7933],
    ],
    // Bus 63: Tour Eiffel → Gare de Lyon, 8 stops
    'Bus 63': [
      [2.2944,48.8588],[2.2923,48.8640],[2.2942,48.8677],[2.2988,48.8709],
      [2.3032,48.8706],[2.3226,48.8494],[2.3734,48.8504],[2.3731,48.8445],
    ],
    // Bus 95: Montrouge → Pont de Levallois, 8 stops
    'Bus 95': [
      [2.3157,48.8129],[2.3326,48.8341],[2.3369,48.8435],[2.3340,48.8536],
      [2.3378,48.8600],[2.3187,48.8840],[2.3120,48.8940],[2.2811,48.8960],
    ],
  },
  Lille: {
    // M1: CHR-B-Calmette (W) → Lomme-Canteleu via Roubaix, 14 stations
    M1: [
      [2.9889,50.6115],[2.9979,50.6155],[3.0098,50.6123],[3.0187,50.6175],
      [3.0368,50.6158],[3.0498,50.6242],[3.0600,50.6276],[3.0621,50.6371],
      [3.0702,50.6363],[3.0736,50.6378],[3.1192,50.6488],[3.1810,50.6947],
      [3.1952,50.7017],[2.9636,50.6569],
    ],
    // M2: Saint-Philibert (E) → CH Dron Tourcoing (N), 13 stations
    M2: [
      [3.1649,50.6397],[3.1390,50.6330],[3.1105,50.6302],[3.0988,50.6231],
      [3.0836,50.6154],[3.0692,50.6086],[3.0654,50.6054],[3.1095,50.6608],
      [3.1397,50.6769],[3.1810,50.6947],[3.1841,50.7017],[3.1845,50.7237],
      [3.1601,50.7339],
    ],
    // Tram R: Tourcoing → Lille Flandres, 11 stops
    'Tram R': [
      [3.1601,50.7213],[3.1650,50.7145],[3.1558,50.7062],[3.1397,50.6769],
      [3.1303,50.6846],[3.1320,50.6939],[3.1810,50.6947],[3.1952,50.7017],
      [3.1972,50.6918],[3.1834,50.6844],[3.0702,50.6363],
    ],
    // L1: Quatre Cantons → CHR, 8 stops
    L1: [
      [3.0654,50.6054],[3.0836,50.6154],[3.0692,50.6086],[3.0632,50.6091],
      [3.0736,50.6378],[3.0702,50.6363],[3.0368,50.6158],[2.9889,50.6115],
    ],
    // L3: Bois-Blancs → Cité Scientifique, 6 stops
    L3: [
      [2.9927,50.6348],[3.0310,50.6319],[3.0702,50.6363],[3.0621,50.6371],
      [3.0736,50.6378],[3.0824,50.6119],
    ],
    // L5: Faches-Thumesnil → Croix-Centre, 6 stops
    L5: [
      [3.0748,50.5831],[3.0883,50.5993],[3.1014,50.6165],[3.1095,50.6390],
      [3.1810,50.6947],[3.1397,50.6769],
    ],
    // Eurostar: Paris → London, 5 stops
    Eurostar: [
      [2.3570,48.8806],[1.8521,50.9513],[3.0702,50.6363],[0.9831,51.4389],
      [-0.1241,51.5316],
    ],
  },
}

// ── Haversine distance (km) between two GPS points ────────────────────────
function haversineKm(lat1, lng1, lat2, lng2) {
  const R  = 6371
  const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180
  const Δφ = (lat2 - lat1) * Math.PI / 180
  const Δλ = (lng2 - lng1) * Math.PI / 180
  const a  = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2
  return R * 2 * Math.asin(Math.sqrt(a))
}

// Typical commercial speed per line type (km/h)
function lineSpeedKmh(line) {
  if (line.name === 'Eurostar') return 280
  if (line.type === 'RER')      return 60
  if (line.type === 'Métro')    return 35
  if (line.type === 'Tramway')  return 22
  return 18 // Bus
}

// ── Vehicle GPS positions (derived from real station coordinates + clock) ──
// Returns vehicles with ETAs at every upcoming station and at the terminus
function getVehiclePositions(line, city, now) {
  const coords = STATION_COORDS[city]?.[line.name]
  const stops  = STATION_DATA[city]?.[line.name]
  if (!coords || !stops || coords.length < 2) return []

  const freq   = isPeak(now) ? line.freq_peak : line.freq_off
  const nowSec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()
  const n      = coords.length
  const hash   = line.name.split('').reduce((a, c) => a + c.charCodeAt(0), 0) + city.length * 7
  const speed  = lineSpeedKmh(line)
  const dwell  = 25 // seconds dwell per station

  const tripSec = n * freq * 30   // approximate one-way trip duration in seconds

  const vehicles = []
  for (let dir = 0; dir < 2; dir++) {
    for (let v = 0; v < 2; v++) {
      const offset = (hash * 1337 + v * freq * 60 + dir * tripSec * 0.5) % tripSec
      const pos    = ((nowSec + offset) % tripSec) / tripSec * (n - 1)
      const i0     = Math.min(Math.floor(pos), n - 2)
      const frac   = pos - i0

      // Reverse direction for dir=1
      const a = dir === 0 ? i0     : (n - 1 - i0)
      const b = dir === 0 ? i0 + 1 : (n - 2 - i0)
      if (a < 0 || a >= n || b < 0 || b >= n) continue

      const [lng0, lat0] = coords[a]
      const [lng1, lat1] = coords[b]
      const lat     = lat0 + (lat1 - lat0) * frac
      const lng     = lng0 + (lng1 - lng0) * frac
      const bearing = Math.round(Math.atan2(lng1 - lng0, lat1 - lat0) * 180 / Math.PI)

      // ── ETA at every upcoming station ─────────────────────────────────
      // Time (seconds) to reach the next station b from current GPS pos
      const distToNext = haversineKm(lat, lng, lat1, lng1)
      let cumSec = (distToNext / speed) * 3600 + dwell

      // Build the ordered list of upcoming station indices (from b to terminus)
      const upcoming = []
      if (dir === 0) { for (let k = b; k < n;     k++) upcoming.push(k) }
      else           { for (let k = b; k >= 0;    k--) upcoming.push(k) }

      const etaStations = []
      for (let ui = 0; ui < upcoming.length; ui++) {
        const k = upcoming[ui]
        if (ui > 0) {
          const prev = upcoming[ui - 1]
          const [lngP, latP] = coords[prev]
          const [lngK, latK] = coords[k]
          const segDist = haversineKm(latP, lngP, latK, lngK)
          cumSec += (segDist / speed) * 3600 + dwell
        }
        etaStations.push({
          idx:     k,
          name:    stops[k] || '',
          etaDate: new Date(now.getTime() + Math.round(cumSec) * 1000),
        })
      }
      const etaTerminus = etaStations.length > 0 ? etaStations[etaStations.length - 1] : null

      vehicles.push({
        id:          `${line.name}-${dir}-${v}`,
        lat:         +lat.toFixed(6),
        lng:         +lng.toFixed(6),
        bearing,
        stopIdx:     a,
        nextStop:    stops[b] || '',
        direction:   dir === 0 ? line.dirB : line.dirA,
        dir,
        etaStations,     // [{idx, name, etaDate}] for every upcoming stop
        etaTerminus,     // {idx, name, etaDate} of terminus arrival
      })
    }
  }
  return vehicles
}

// ── Build Mapbox Static Images URL ─────────────────────────────────────────
function buildMapUrl(line, city, vehicles, token) {
  const coords = STATION_COORDS[city]?.[line.name]
  if (!coords || !token || vehicles.length === 0) return null

  const col = line.color.replace('#', '')

  // Route as GeoJSON LineString + vehicle Point markers
  const features = [
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: { stroke: line.color, 'stroke-width': 4, 'stroke-opacity': 0.55 },
    },
    ...vehicles.map(v => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [v.lng, v.lat] },
      properties: { 'marker-color': line.color, 'marker-symbol': 'rail', 'marker-size': 'large' },
    })),
  ]

  const geojson  = JSON.stringify({ type: 'FeatureCollection', features })
  const encoded  = encodeURIComponent(geojson)
  return `https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/geojson(${encoded})/auto/560x200?padding=35,15,35,15&access_token=${token}`
}

// ── Arrival computation ────────────────────────────────────────────────────
function isPeak(date) {
  const h = date.getHours()
  return (h >= 7 && h <= 9) || (h >= 17 && h <= 20)
}

function getNextArrivals(line, now, count = 4) {
  const freq = isPeak(now) ? line.freq_peak : line.freq_off
  const min  = Math.floor(now.getTime() / 60000)
  const hash = line.name.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  const phase = ((min + hash) % freq) / freq
  const off   = (1 - phase) * freq
  return Array.from({ length: count }, (_, i) =>
    new Date(now.getTime() + (off + i * freq) * 60000)
  )
}

const fmtHM = (d) => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

function etaLabel(d, now) {
  const diff = Math.round((d - now) / 60000)
  if (diff <= 0) return 'À quai'
  if (diff === 1) return '1 min'
  return `${diff} min`
}

// ── Line row ──────────────────────────────────────────────────────────────
function LineRow({ line, statusInfo, now, onClick }) {
  const arrivals = getNextArrivals(line, now)
  const freq     = isPeak(now) ? line.freq_peak : line.freq_off
  const st       = statusInfo?.network_status || 'NORMAL'
  const stCol    = STATUS_COL[st] || '#22c55e'
  const msg      = statusInfo?.most_severe_message

  return (
    <div
      title={msg || undefined}
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 12px', borderRadius: 8, marginBottom: 4,
        background: 'var(--bg)', border: '1px solid var(--border)',
        borderLeft: `4px solid ${line.color}`,
        cursor: 'pointer', transition: 'background 0.12s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
      onMouseLeave={e => e.currentTarget.style.background = 'var(--bg)'}
    >
      {/* Badge */}
      <span style={{
        background: line.color, color: line.text,
        borderRadius: 6, padding: '3px 8px', fontWeight: 900,
        fontSize: '0.78rem', minWidth: 52, textAlign: 'center', flexShrink: 0,
      }}>
        {line.name}
      </span>

      {/* Direction */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: '0.76rem', color: '#cbd5e1', fontWeight: 500,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {line.dirA}
          <span style={{ color: '#334155', margin: '0 4px' }}>↔</span>
          {line.dirB}
        </div>
        <div style={{ fontSize: '0.62rem', color: '#475569', marginTop: 1 }}>
          toutes les {freq} min
        </div>
      </div>

      {/* Next arrivals */}
      <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
        {arrivals.map((arr, i) => (
          <div key={i} style={{
            textAlign: 'center', borderRadius: 6, padding: '2px 7px', minWidth: 42,
            background: i === 0 ? `${line.color}22` : 'transparent',
            border: `1px solid ${i === 0 ? `${line.color}66` : '#1e293b'}`,
          }}>
            <div style={{ fontSize: '0.58rem', color: '#475569', lineHeight: 1.4 }}>
              {fmtHM(arr)}
            </div>
            <div style={{
              fontSize: '0.72rem', fontWeight: 700, lineHeight: 1.4,
              color: i === 0 ? line.color : '#475569',
            }}>
              {etaLabel(arr, now)}
            </div>
          </div>
        ))}
      </div>

      {/* Status */}
      <span style={{
        padding: '2px 8px', borderRadius: 999, fontSize: '0.65rem',
        fontWeight: 700, background: `${stCol}18`, color: stCol,
        border: `1px solid ${stCol}44`, flexShrink: 0,
        cursor: msg ? 'help' : 'default',
      }}>
        {st === 'DISRUPTED' ? '⚠ Perturbé' : st === 'REDUCED' ? '⚡ Réduit' : '✓ Normal'}
      </span>
      <span style={{ fontSize: '0.62rem', color: '#334155', flexShrink: 0 }}>▶</span>
    </div>
  )
}

// ── City panel ────────────────────────────────────────────────────────────
function CityPanel({ network, apiLines, now, city, onLineClick }) {
  const statusMap = {}
  if (apiLines) apiLines.forEach(l => { statusMap[l.line_name] = l })

  const byType = {}
  network.forEach(l => {
    if (!byType[l.type]) byType[l.type] = []
    byType[l.type].push(l)
  })

  return (
    <div>
      {TYPE_ORDER.filter(type => byType[type]).map(type => (
        <div key={type} style={{ marginBottom: 18 }}>
          <div style={{
            fontSize: '0.68rem', fontWeight: 700, color: '#475569',
            textTransform: 'uppercase', letterSpacing: '0.08em',
            marginBottom: 6, paddingLeft: 2,
          }}>
            {TYPE_ICON[type]} {type}
          </div>
          {byType[type].map(line => (
            <LineRow
              key={line.name}
              line={line}
              statusInfo={statusMap[line.name]}
              now={now}
              onClick={() => onLineClick({ line, statusInfo: statusMap[line.name] })}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Line detail modal ─────────────────────────────────────────────────────
function LineDetail({ line, city, statusInfo, now, mapboxToken, onClose }) {
  const [liveClock, setLiveClock] = useState(now)
  useEffect(() => {
    setLiveClock(new Date())
    const t = setInterval(() => setLiveClock(new Date()), 15_000)
    return () => clearInterval(t)
  }, [])

  const stops    = STATION_DATA[city]?.[line.name] || []
  const vehicles = getVehiclePositions(line, city, liveClock)
  const mapUrl   = buildMapUrl(line, city, vehicles, mapboxToken)
  const st       = statusInfo?.network_status || 'NORMAL'
  const stCol    = STATUS_COL[st] || '#22c55e'
  const freq     = isPeak(liveClock) ? line.freq_peak : line.freq_off

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#1e293b', borderRadius: 16, border: '1px solid #334155',
          width: '100%', maxWidth: 520, maxHeight: '88vh',
          overflow: 'hidden', display: 'flex', flexDirection: 'column',
          boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid #334155',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{
            background: line.color, color: line.text,
            borderRadius: 8, padding: '6px 14px', fontWeight: 900, fontSize: '1rem', flexShrink: 0,
          }}>
            {line.name}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, color: '#f1f5f9', fontSize: '0.95rem' }}>
              {TYPE_ICON[line.type]} {line.type}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {line.dirA} ↔ {line.dirB}
            </div>
          </div>
          <span style={{
            padding: '3px 10px', borderRadius: 999, fontSize: '0.68rem', fontWeight: 700,
            background: `${stCol}20`, color: stCol, border: `1px solid ${stCol}44`, flexShrink: 0,
          }}>
            {st === 'DISRUPTED' ? '⚠ Perturbé' : st === 'REDUCED' ? '⚡ Réduit' : '✓ Normal'}
          </span>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#475569', cursor: 'pointer',
            fontSize: '1.1rem', padding: '2px 6px', flexShrink: 0, lineHeight: 1,
          }}>✕</button>
        </div>

        {/* Info bar */}
        <div style={{
          padding: '9px 20px', background: '#162032', borderBottom: '1px solid #334155',
          display: 'flex', gap: 20, fontSize: '0.73rem', color: '#64748b', flexWrap: 'wrap',
        }}>
          <span>🕐 {isPeak(liveClock) ? 'Heure de pointe' : 'Hors pointe'} · toutes les {freq} min</span>
          <span>📍 {stops.length || '—'} arrêts</span>
          <span>🚆 {vehicles.length} véhicules en service</span>
          {statusInfo?.most_severe_message && (
            <span style={{ color: '#f59e0b' }}>⚠ {statusInfo.most_severe_message}</span>
          )}
        </div>

        {/* Mapbox GPS mini-map */}
        {mapUrl && (
          <div style={{ padding: '12px 20px 0', borderBottom: '1px solid #1e293b' }}>
            <div style={{ fontSize: '0.65rem', color: '#475569', marginBottom: 5, display: 'flex', justifyContent: 'space-between' }}>
              <span>📡 Positions GPS temps réel · actualisation 15 s</span>
              <span style={{ color: '#334155' }}>
                {liveClock.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
            <img
              src={mapUrl}
              alt={`Carte GPS ${line.name}`}
              style={{ width: '100%', borderRadius: 8, display: 'block', minHeight: 120 }}
              onError={e => { e.currentTarget.style.display = 'none' }}
            />
            {/* GPS coordinate badges */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 7, marginBottom: 4 }}>
              {vehicles.map(v => (
                <span key={v.id} style={{
                  fontSize: '0.63rem', padding: '2px 8px', borderRadius: 999,
                  background: v.dir === 0 ? line.color : `${line.color}28`,
                  color: v.dir === 0 ? line.text : line.color,
                  border: v.dir === 0 ? 'none' : `1px solid ${line.color}60`,
                  fontFamily: 'monospace',
                }}>
                  🚆 {v.lat}°N {v.lng}°E → {(v.direction || '').split(/[\s/]/)[0]}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Terminus arrivals ─────────────────────────────────────────── */}
        {vehicles.some(v => v.etaTerminus) && (
          <div style={{
            padding: '10px 20px 12px', borderBottom: '1px solid #334155',
            background: '#0f172a',
          }}>
            <div style={{ fontSize: '0.63rem', color: '#64748b', marginBottom: 7, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              🏁 Arrivée prévue au terminus
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {vehicles.filter(v => v.etaTerminus).map(v => {
                const t    = v.etaTerminus
                const minsLeft = Math.max(0, Math.round((t.etaDate - liveClock) / 60000))
                return (
                  <div key={v.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{
                      padding: '2px 10px', borderRadius: 999, fontSize: '0.67rem', fontWeight: 800,
                      background: v.dir === 0 ? line.color : `${line.color}22`,
                      color: v.dir === 0 ? line.text : line.color,
                      border: v.dir === 0 ? 'none' : `1px solid ${line.color}55`,
                      flexShrink: 0,
                    }}>
                      🚆 → {(v.direction || '').split(/[\s/]/)[0]}
                    </span>
                    <span style={{ fontSize: '0.97rem', fontWeight: 800, color: '#f1f5f9', flexShrink: 0, fontFamily: 'monospace' }}>
                      {t.etaDate.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {t.name} · dans {minsLeft} min
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Route */}
        <div style={{ overflowY: 'auto', padding: '16px 20px 16px 40px', flex: 1 }}>
          {stops.length === 0 ? (
            <div style={{ color: '#475569', textAlign: 'center', padding: 40, fontSize: '0.85rem' }}>
              Données de trajet non disponibles
            </div>
          ) : (
            <div style={{ position: 'relative' }}>
              {/* Vertical rail */}
              <div style={{
                position: 'absolute', left: -22, top: 8, bottom: 8,
                width: 4, background: line.color, borderRadius: 2, opacity: 0.55,
              }} />

              {stops.map((stop, idx) => {
                const vehs = vehicles.filter(v => v.stopIdx === idx)

                // Vehicles approaching this station (ETAs within the next 20 min)
                const cutoff   = new Date(liveClock.getTime() + 20 * 60 * 1000)
                const arriving = vehicles
                  .map(v => {
                    const e = v.etaStations?.find(es => es.idx === idx)
                    return e ? { veh: v, etaDate: e.etaDate } : null
                  })
                  .filter(x => x && x.etaDate <= cutoff)
                  .sort((a, b) => a.etaDate - b.etaDate)

                const isTerminus  = idx === 0 || idx === stops.length - 1
                const hasActivity = vehs.length > 0 || arriving.length > 0

                return (
                  <div key={idx} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    paddingBottom: idx < stops.length - 1 ? 13 : 0,
                    position: 'relative',
                  }}>
                    {/* Station dot */}
                    <div style={{
                      position: 'absolute', left: -29,
                      width: isTerminus ? 14 : 10, height: isTerminus ? 14 : 10,
                      borderRadius: '50%',
                      background: isTerminus ? line.color : '#1e293b',
                      border: `2.5px solid ${line.color}`,
                      zIndex: 1,
                      boxShadow: isTerminus ? `0 0 0 4px ${line.color}25` : 'none',
                    }} />

                    {/* Name */}
                    <div style={{ flex: 1 }}>
                      <span style={{
                        fontSize: isTerminus ? '0.88rem' : '0.8rem',
                        fontWeight: isTerminus ? 700 : 400,
                        color: isTerminus ? '#f1f5f9' : hasActivity ? '#e2e8f0' : '#94a3b8',
                      }}>
                        {stop}
                      </span>
                      {isTerminus && (
                        <span style={{ marginLeft: 8, fontSize: '0.6rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                          TERMINUS
                        </span>
                      )}
                    </div>

                    {/* Vehicle badges: currently passing + ETAs */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-end', flexShrink: 0 }}>
                      {/* Currently between this station and next */}
                      {vehs.map(v => (
                        <span key={v.id} style={{
                          padding: '2px 9px', borderRadius: 999, fontSize: '0.64rem', fontWeight: 800,
                          background: v.dir === 0 ? line.color : `${line.color}30`,
                          color: v.dir === 0 ? line.text : line.color,
                          border: v.dir === 0 ? 'none' : `1px solid ${line.color}70`,
                        }}>
                          🚆 en transit → {(v.dir === 0 ? line.dirB : line.dirA)?.split(/[\s/]/)[0]}
                        </span>
                      ))}
                      {/* Approaching vehicles with ETA */}
                      {arriving.map(({ veh: v, etaDate }) => {
                        const minsLeft = Math.max(0, Math.round((etaDate - liveClock) / 60000))
                        return (
                          <span key={`eta-${v.id}`} style={{
                            padding: '2px 9px', borderRadius: 999, fontSize: '0.63rem', fontWeight: 700,
                            background: 'transparent',
                            color: '#94a3b8',
                            border: `1px solid #334155`,
                            fontFamily: 'monospace',
                          }}>
                            ⏱ {etaDate.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })} · {minsLeft === 0 ? 'imm.' : `${minsLeft} min`}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '9px 20px', borderTop: '1px solid #334155',
          background: '#162032', display: 'flex', justifyContent: 'space-between',
          fontSize: '0.67rem', color: '#475569',
        }}>
          <span>Positions GPS · coordonnées RATP réelles · ↺ 15 s</span>
          <span>{liveClock.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>
    </div>
  )
}

// ── Summary strip ─────────────────────────────────────────────────────────
function SummaryStrip({ network, apiLines, now }) {
  const statusMap = {}
  if (apiLines) apiLines.forEach(l => { statusMap[l.line_name] = l })

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
      {TYPE_ORDER.filter(type => network.some(l => l.type === type)).map(type => {
        const tLines    = network.filter(l => l.type === type)
        const disrupted = tLines.filter(l => statusMap[l.name]?.network_status === 'DISRUPTED').length
        const reduced   = tLines.filter(l => statusMap[l.name]?.network_status === 'REDUCED').length

        return (
          <div key={type} style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '10px 14px', flex: '1 1 100px',
          }}>
            <div style={{ fontSize: '0.68rem', color: '#64748b' }}>
              {TYPE_ICON[type]} {type}
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f1f5f9', margin: '2px 0' }}>
              {tLines.length}
            </div>
            <div style={{ fontSize: '0.65rem' }}>
              {disrupted > 0 && <span style={{ color: '#ef4444' }}>{disrupted} pert.&nbsp;</span>}
              {reduced   > 0 && <span style={{ color: '#f59e0b' }}>{reduced} réduit.&nbsp;</span>}
              {disrupted === 0 && reduced === 0 && <span style={{ color: '#22c55e' }}>Normal</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────
export default function Transit() {
  const [city, setCity] = useState('Paris')
  const [now,  setNow]  = useState(new Date())
  const [selected, setSelected] = useState(null)   // { line, statusInfo }
  const { data: transitLines } = useApi('/transit/lines', 60_000)
  const { data: cfgData }      = useApi('/config', 0)
  const mapboxToken = cfgData?.mapbox_token || ''

  // Refresh clock every 30 s so ETAs stay current
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000)
    return () => clearInterval(t)
  }, [])

  const network  = city === 'Paris' ? PARIS_NETWORK : LILLE_NETWORK
  const apiLines = transitLines?.filter(l => l.city === city) ?? []
  const peak     = isPeak(now)

  const disrupted = apiLines.filter(l => l.network_status === 'DISRUPTED').length
  const reduced   = apiLines.filter(l => l.network_status === 'REDUCED').length

  return (
    <div className="page-body">

      {/* ── Line detail modal ── */}
      {selected && (
        <LineDetail
          line={selected.line}
          city={city}
          statusInfo={selected.statusInfo}
          now={now}
          mapboxToken={mapboxToken}
          onClose={() => setSelected(null)}
        />
      )}

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
            Réseau de transport — {city}
          </h2>
          <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: 4 }}>
            Prochains passages &nbsp;·&nbsp;
            {now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
            &nbsp;·&nbsp;
            <span style={{ color: peak ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
              {peak ? '🔴 Heure de pointe' : '🟢 Hors pointe'}
            </span>
            {(disrupted > 0 || reduced > 0) && (
              <span style={{ marginLeft: 8, color: '#f97316' }}>
                &nbsp;·&nbsp; ⚠ {disrupted + reduced} ligne{disrupted + reduced > 1 ? 's' : ''} affectée{disrupted + reduced > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* City tabs */}
        <div style={{ display: 'flex', gap: 6 }}>
          {['Paris', 'Lille'].map(c => (
            <button
              key={c}
              onClick={() => setCity(c)}
              style={{
                padding: '7px 20px', borderRadius: 8, fontWeight: 700, fontSize: '0.85rem',
                border: 'none', cursor: 'pointer', transition: 'all 0.15s',
                background: city === c ? '#6366f1' : 'var(--surface)',
                color: city === c ? '#fff' : '#64748b',
              }}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* ── Summary strip ── */}
      <SummaryStrip network={network} apiLines={apiLines} now={now} />

      {/* ── Timetable ── */}
      <div className="table-card">
        <div className="table-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Prochains passages</span>
          <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 400 }}>
            {network.length} lignes &nbsp;·&nbsp; mis à jour toutes les 30 s &nbsp;·&nbsp;
            <span style={{ color: '#64748b', fontStyle: 'italic' }}>cliquez sur une ligne pour le détail</span>
          </span>
        </div>
        <div style={{ padding: '10px 0 4px' }}>
          <CityPanel network={network} apiLines={apiLines} now={now} city={city} onLineClick={setSelected} />
        </div>
      </div>

    </div>
  )
}
