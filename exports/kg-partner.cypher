// AM2Scale dataspace knowledge graph
// Sichtbarkeitsstufe: T2 (Partner)
// Erzeugt von ui/discovery/export_neo4j.py

// vorherigen Import entfernen
MATCH (n:KG) DETACH DELETE n;

// ===== consumer  (Dataset: WienEnergie) =====
CREATE (:KG:Unternehmen {id: 'unternehmen:U3', owner: 'consumer', kgType: 'Unternehmen', tier: 1, sichtbar: 7, verborgen: 0, stufe: 2, uId: 'U3', name: 'WienEnergie', stadt: 'Wien', land: 'Austria', strasse: '1.Haidequerstraße 1', stromtarif: 0.05, co2PerKwh: 0.1});


// ===== huber-ag  (Dataset: OEBB) =====
CREATE (:KG:Produktionsauftrag {id: 'auftrag:B-001', owner: 'huber-ag', kgType: 'Produktionsauftrag', tier: 1, sichtbar: 14, verborgen: 0, stufe: 2, auftragId: 'B-001', materialnummer: '000000075612247', druckmaterial: 'PC-ABS FR', anzahlTeile: 30, teileProJob: 2, druckzeitProTeil: 9, druckzeitJob: 18, druckzeitGesamt: 270, materialverbrauchJob: 120, materialGramm: 50, durchsatz: 6.666666666666667, anzahlJobs: 15, istTeile: 30, teileDiff: 0});
CREATE (:KG:Bauteil {id: 'bauteil:000000075612247', owner: 'huber-ag', kgType: 'Bauteil', tier: 1, sichtbar: 22, verborgen: 4, stufe: 2, materialnummer: '000000075612247', materialkurztext: 'SchneeschutzgitterØ220mmf.Tyfon,CJ', benennung: 'Schneeschutzgitter Ø 220 für Tyfon', kurztext: 'Schneeschutzgitter', werkstoff: 'X5CrNi18-10 - 1.4301', normBezeichnung: 'EN 10088-3', abmessung: '95XØ202MM', laenge: 0, breite: 0, hoehe: 0, volumen: 0, nettogewicht: 0.25, bruttogewicht: 0.25, gewichtseinheit: 'KG', bestandsmenge: 5, bestandswert: 5, sicherheitsbestand: 2.2, planlieferzeit: 90, preis: 163.766, lieferant: 'KNORR-BREMSE', ersteller: 'Knorr-Bremse [129]', edcAssetId: 'stammdaten-000000075612247', withheld: ['Dokumentnummer', 'Ersteller-SachNr', 'Identnummer', 'Zeichnungsnummer (Hersteller)']});
CREATE (:KG:Drucker {id: 'drucker:P1', owner: 'huber-ag', kgType: 'Drucker', tier: 1, sichtbar: 3, verborgen: 1, stufe: 2, printId: 'P1', herstellerName: 'Stratasys', modell: 'Stratasys_F170', withheld: ['Seriennummer']});
CREATE (:KG:DPP {id: 'dpp:DPP-000000075612247', owner: 'huber-ag', kgType: 'DPP', tier: 1, sichtbar: 6, verborgen: 4, stufe: 2, materialnummer: '000000075612247', version: 'v1.1', druckdatum: '[Maschinendaten]', co2Herstellung: 'kWh [Maschinendaten] * CO2/kWh [UNternehmensaten]', co2Betrieb: 'kWh [Betrieb/Remanufacturing] * CO2/kWh [UNternehmensaten]', dppId: 'DPP-000000075612247', withheld: ['Anmerkung', 'Bearbeiter', 'Chargen-ID', 'Ereignis/Änderung']});
CREATE (:KG:Fertigungsdaten {id: 'charge:P1', owner: 'huber-ag', kgType: 'Fertigungsdaten', tier: 1, sichtbar: 5, verborgen: 1, stufe: 2, chargeId: 'CHG-P1', printId: 'P1', messwerte: 1514, zeitraumVon: '2026-07-02T00:00:00', zeitraumBis: '2026-07-02T00:00:00', withheld: ['Rohdaten-Referenz']});
CREATE (:KG:Unternehmen {id: 'unternehmen:U1', owner: 'huber-ag', kgType: 'Unternehmen', tier: 1, sichtbar: 7, verborgen: 0, stufe: 2, uId: 'U1', name: 'OEBB', stadt: 'Wien', land: 'Austria', strasse: 'Grillgasse 48', stromtarif: 0.1, co2PerKwh: 0.05});

MATCH (a:KG {id: 'unternehmen:U1', owner: 'huber-ag'}), (b:KG {id: 'drucker:P1', owner: 'huber-ag'}) CREATE (a)-[:BETREIBT]->(b);
MATCH (a:KG {id: 'unternehmen:U1', owner: 'huber-ag'}), (b:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}) CREATE (a)-[:FERTIGT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}) CREATE (a)-[:FUER]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'drucker:P1', owner: 'huber-ag'}) CREATE (a)-[:LAEUFT_AUF]->(b);
MATCH (a:KG {id: 'drucker:P1', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:LIEFERT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:ERZEUGT]->(b);
MATCH (a:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}), (b:KG {id: 'dpp:DPP-000000075612247', owner: 'huber-ag'}) CREATE (a)-[:HAT_DPP]->(b);
MATCH (a:KG {id: 'dpp:DPP-000000075612247', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:BASIERT_AUF]->(b);

// ===== provider  (Dataset: WienerLinien) =====
CREATE (:KG:Unternehmen {id: 'unternehmen:U2', owner: 'provider', kgType: 'Unternehmen', tier: 1, sichtbar: 7, verborgen: 0, stufe: 2, uId: 'U2', name: 'WienerLinien', stadt: 'Wien', land: 'Austria', strasse: 'Erdbergstraße 202', stromtarif: 0.08, co2PerKwh: 0.1});


// ===== rheinmetall  (Dataset: WienerNetze) =====
CREATE (:KG:Unternehmen {id: 'unternehmen:U4', owner: 'rheinmetall', kgType: 'Unternehmen', tier: 1, sichtbar: 7, verborgen: 0, stufe: 2, uId: 'U4', name: 'WienerNetze', stadt: 'Wien', land: 'Austria', strasse: 'Nussbaumallee 21', stromtarif: 0.05, co2PerKwh: 0.1});


// ---- nützliche Abfragen (im Neo4j Browser einzeln ausführen) ----
// alles anzeigen:            MATCH (n:KG)-[r]->(m:KG) RETURN n, r, m;
// ein Unternehmen:           MATCH (n:KG {owner:'huber-ag'})-[r]->(m) RETURN n,r,m;
// Bauteile mit Werkstoff:    MATCH (b:Bauteil) RETURN b.owner, b.benennung, b.werkstoff, b.abmessung;
// Herkunftskette eines DPP:  MATCH p=(d:DPP)-[*1..3]-(x:KG) RETURN p;
// was verbirgt dieses Level: MATCH (n:KG) WHERE n.verborgen > 0 RETURN n.owner, n.kgType, n.sichtbar, n.verborgen, n.withheld ORDER BY n.verborgen DESC;
