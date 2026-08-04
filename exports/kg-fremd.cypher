// AM2Scale dataspace knowledge graph
// Sichtbarkeitsstufe: T1 (fremd)
// Erzeugt von ui/discovery/export_neo4j.py

// vorherigen Import entfernen
MATCH (n:KG) DETACH DELETE n;

// ===== consumer  (Dataset: WienEnergie) =====
CREATE (:KG:Produktionsauftrag {id: 'auftrag:B-001', owner: 'consumer', kgType: 'Produktionsauftrag', tier: 1, sichtbar: 3, verborgen: 11, stufe: 1, auftragId: 'B-001', materialnummer: '000000075612247', druckmaterial: 'PC-ABS FR', withheld: ['Anzahl Jobs', 'Anzahl Teile', 'Druckzeit gesamt', 'Druckzeit pro Job', 'Druckzeit pro Teil', 'Durchsatz', 'IST-Teile', 'Material (g)', 'Netto-Materialverbrauch pro Job', 'Teile pro Job', 'Teile-Differenz']});
CREATE (:KG:Drucker {id: 'drucker:P1', owner: 'consumer', kgType: 'Drucker', tier: 1, sichtbar: 3, verborgen: 1, stufe: 1, printId: 'P1', herstellerName: 'Stratasys', modell: 'Stratasys_F170', withheld: ['Seriennummer']});
CREATE (:KG:Bauteil {id: 'bauteil:000000075612247', owner: 'consumer', kgType: 'Bauteil', tier: 1, sichtbar: 14, verborgen: 11, stufe: 1, materialnummer: '000000075612247', materialkurztext: 'SchneeschutzgitterØ220mmf.Tyfon,CJ', benennung: 'Schneeschutzgitter Ø 220 für Tyfon', kurztext: 'Schneeschutzgitter', werkstoff: 'X5CrNi18-10 - 1.4301', normBezeichnung: 'EN 10088-3', abmessung: '95XØ202MM', laenge: 0, breite: 0, hoehe: 0, volumen: 0, nettogewicht: 0.25, bruttogewicht: 0.25, gewichtseinheit: 'KG', withheld: ['Bestandsmenge', 'Bestandswert', 'Dokumentnummer', 'Ersteller', 'Ersteller-SachNr', 'Identnummer', 'Lieferant', 'Planlieferzeit (Ø)', 'Preis', 'Sicherheitsbestand (Ø)', 'Zeichnungsnummer (Hersteller)']});
CREATE (:KG:Unternehmen {id: 'unternehmen:U3', owner: 'consumer', kgType: 'Unternehmen', tier: 1, sichtbar: 4, verborgen: 3, stufe: 1, uId: 'U3', name: 'WienEnergie', stadt: 'Wien', land: 'Austria', withheld: ['CO₂ pro kWh', 'Straße', 'Stromtarif (€/kWh)']});
CREATE (:KG:DPP {id: 'dpp:DPP-000000075612247', owner: 'consumer', kgType: 'DPP', tier: 1, sichtbar: 3, verborgen: 7, stufe: 1, materialnummer: '000000075612247', version: 'v1.1', dppId: 'DPP-000000075612247', withheld: ['Anmerkung', 'Bearbeiter', 'CO₂ Herstellung', 'CO₂ in Betrieb', 'Chargen-ID', 'Druckdatum', 'Ereignis/Änderung']});
CREATE (:KG:Fertigungsdaten {id: 'charge:P1', owner: 'consumer', kgType: 'Fertigungsdaten', tier: 1, sichtbar: 2, verborgen: 4, stufe: 1, chargeId: 'CHG-P1', printId: 'P1', withheld: ['Anzahl Messwerte', 'Rohdaten-Referenz', 'Zeitraum bis', 'Zeitraum von']});

MATCH (a:KG {id: 'unternehmen:U3', owner: 'consumer'}), (b:KG {id: 'drucker:P1', owner: 'consumer'}) CREATE (a)-[:BETREIBT]->(b);
MATCH (a:KG {id: 'unternehmen:U3', owner: 'consumer'}), (b:KG {id: 'bauteil:000000075612247', owner: 'consumer'}) CREATE (a)-[:FERTIGT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'consumer'}), (b:KG {id: 'bauteil:000000075612247', owner: 'consumer'}) CREATE (a)-[:FUER]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'consumer'}), (b:KG {id: 'drucker:P1', owner: 'consumer'}) CREATE (a)-[:LAEUFT_AUF]->(b);
MATCH (a:KG {id: 'drucker:P1', owner: 'consumer'}), (b:KG {id: 'charge:P1', owner: 'consumer'}) CREATE (a)-[:LIEFERT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'consumer'}), (b:KG {id: 'charge:P1', owner: 'consumer'}) CREATE (a)-[:ERZEUGT]->(b);
MATCH (a:KG {id: 'bauteil:000000075612247', owner: 'consumer'}), (b:KG {id: 'dpp:DPP-000000075612247', owner: 'consumer'}) CREATE (a)-[:HAT_DPP]->(b);
MATCH (a:KG {id: 'dpp:DPP-000000075612247', owner: 'consumer'}), (b:KG {id: 'charge:P1', owner: 'consumer'}) CREATE (a)-[:BASIERT_AUF]->(b);

// ===== huber-ag  (Dataset: OEBB) =====
CREATE (:KG:Produktionsauftrag {id: 'auftrag:B-001', owner: 'huber-ag', kgType: 'Produktionsauftrag', tier: 1, sichtbar: 3, verborgen: 11, stufe: 1, auftragId: 'B-001', materialnummer: '000000075612247', druckmaterial: 'PC-ABS FR', withheld: ['Anzahl Jobs', 'Anzahl Teile', 'Druckzeit gesamt', 'Druckzeit pro Job', 'Druckzeit pro Teil', 'Durchsatz', 'IST-Teile', 'Material (g)', 'Netto-Materialverbrauch pro Job', 'Teile pro Job', 'Teile-Differenz']});
CREATE (:KG:Drucker {id: 'drucker:P1', owner: 'huber-ag', kgType: 'Drucker', tier: 1, sichtbar: 3, verborgen: 1, stufe: 1, printId: 'P1', herstellerName: 'Stratasys', modell: 'Stratasys_F170', withheld: ['Seriennummer']});
CREATE (:KG:Bauteil {id: 'bauteil:000000075612247', owner: 'huber-ag', kgType: 'Bauteil', tier: 1, sichtbar: 14, verborgen: 11, stufe: 1, materialnummer: '000000075612247', materialkurztext: 'SchneeschutzgitterØ220mmf.Tyfon,CJ', benennung: 'Schneeschutzgitter Ø 220 für Tyfon', kurztext: 'Schneeschutzgitter', werkstoff: 'X5CrNi18-10 - 1.4301', normBezeichnung: 'EN 10088-3', abmessung: '95XØ202MM', laenge: 0, breite: 0, hoehe: 0, volumen: 0, nettogewicht: 0.25, bruttogewicht: 0.25, gewichtseinheit: 'KG', withheld: ['Bestandsmenge', 'Bestandswert', 'Dokumentnummer', 'Ersteller', 'Ersteller-SachNr', 'Identnummer', 'Lieferant', 'Planlieferzeit (Ø)', 'Preis', 'Sicherheitsbestand (Ø)', 'Zeichnungsnummer (Hersteller)']});
CREATE (:KG:DPP {id: 'dpp:DPP-000000075612247', owner: 'huber-ag', kgType: 'DPP', tier: 1, sichtbar: 3, verborgen: 7, stufe: 1, materialnummer: '000000075612247', version: 'v1.1', dppId: 'DPP-000000075612247', withheld: ['Anmerkung', 'Bearbeiter', 'CO₂ Herstellung', 'CO₂ in Betrieb', 'Chargen-ID', 'Druckdatum', 'Ereignis/Änderung']});
CREATE (:KG:Fertigungsdaten {id: 'charge:P1', owner: 'huber-ag', kgType: 'Fertigungsdaten', tier: 1, sichtbar: 2, verborgen: 4, stufe: 1, chargeId: 'CHG-P1', printId: 'P1', withheld: ['Anzahl Messwerte', 'Rohdaten-Referenz', 'Zeitraum bis', 'Zeitraum von']});
CREATE (:KG:Unternehmen {id: 'unternehmen:U1', owner: 'huber-ag', kgType: 'Unternehmen', tier: 1, sichtbar: 4, verborgen: 3, stufe: 1, uId: 'U1', name: 'OEBB', stadt: 'Wien', land: 'Austria', withheld: ['CO₂ pro kWh', 'Straße', 'Stromtarif (€/kWh)']});

MATCH (a:KG {id: 'unternehmen:U1', owner: 'huber-ag'}), (b:KG {id: 'drucker:P1', owner: 'huber-ag'}) CREATE (a)-[:BETREIBT]->(b);
MATCH (a:KG {id: 'unternehmen:U1', owner: 'huber-ag'}), (b:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}) CREATE (a)-[:FERTIGT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}) CREATE (a)-[:FUER]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'drucker:P1', owner: 'huber-ag'}) CREATE (a)-[:LAEUFT_AUF]->(b);
MATCH (a:KG {id: 'drucker:P1', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:LIEFERT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:ERZEUGT]->(b);
MATCH (a:KG {id: 'bauteil:000000075612247', owner: 'huber-ag'}), (b:KG {id: 'dpp:DPP-000000075612247', owner: 'huber-ag'}) CREATE (a)-[:HAT_DPP]->(b);
MATCH (a:KG {id: 'dpp:DPP-000000075612247', owner: 'huber-ag'}), (b:KG {id: 'charge:P1', owner: 'huber-ag'}) CREATE (a)-[:BASIERT_AUF]->(b);

// ===== provider  (Dataset: WienerLinien) =====
CREATE (:KG:Produktionsauftrag {id: 'auftrag:B-001', owner: 'provider', kgType: 'Produktionsauftrag', tier: 1, sichtbar: 3, verborgen: 11, stufe: 1, auftragId: 'B-001', materialnummer: '000000075612247', druckmaterial: 'PC-ABS FR', withheld: ['Anzahl Jobs', 'Anzahl Teile', 'Druckzeit gesamt', 'Druckzeit pro Job', 'Druckzeit pro Teil', 'Durchsatz', 'IST-Teile', 'Material (g)', 'Netto-Materialverbrauch pro Job', 'Teile pro Job', 'Teile-Differenz']});
CREATE (:KG:Unternehmen {id: 'unternehmen:U2', owner: 'provider', kgType: 'Unternehmen', tier: 1, sichtbar: 4, verborgen: 3, stufe: 1, uId: 'U2', name: 'WienerLinien', stadt: 'Wien', land: 'Austria', withheld: ['CO₂ pro kWh', 'Straße', 'Stromtarif (€/kWh)']});
CREATE (:KG:Drucker {id: 'drucker:P1', owner: 'provider', kgType: 'Drucker', tier: 1, sichtbar: 3, verborgen: 1, stufe: 1, printId: 'P1', herstellerName: 'Stratasys', modell: 'Stratasys_F170', withheld: ['Seriennummer']});
CREATE (:KG:Bauteil {id: 'bauteil:000000075612247', owner: 'provider', kgType: 'Bauteil', tier: 1, sichtbar: 14, verborgen: 11, stufe: 1, materialnummer: '000000075612247', materialkurztext: 'SchneeschutzgitterØ220mmf.Tyfon,CJ', benennung: 'Schneeschutzgitter Ø 220 für Tyfon', kurztext: 'Schneeschutzgitter', werkstoff: 'X5CrNi18-10 - 1.4301', normBezeichnung: 'EN 10088-3', abmessung: '95XØ202MM', laenge: 0, breite: 0, hoehe: 0, volumen: 0, nettogewicht: 0.25, bruttogewicht: 0.25, gewichtseinheit: 'KG', withheld: ['Bestandsmenge', 'Bestandswert', 'Dokumentnummer', 'Ersteller', 'Ersteller-SachNr', 'Identnummer', 'Lieferant', 'Planlieferzeit (Ø)', 'Preis', 'Sicherheitsbestand (Ø)', 'Zeichnungsnummer (Hersteller)']});
CREATE (:KG:DPP {id: 'dpp:DPP-000000075612247', owner: 'provider', kgType: 'DPP', tier: 1, sichtbar: 3, verborgen: 7, stufe: 1, materialnummer: '000000075612247', version: 'v1.1', dppId: 'DPP-000000075612247', withheld: ['Anmerkung', 'Bearbeiter', 'CO₂ Herstellung', 'CO₂ in Betrieb', 'Chargen-ID', 'Druckdatum', 'Ereignis/Änderung']});
CREATE (:KG:Fertigungsdaten {id: 'charge:P1', owner: 'provider', kgType: 'Fertigungsdaten', tier: 1, sichtbar: 2, verborgen: 4, stufe: 1, chargeId: 'CHG-P1', printId: 'P1', withheld: ['Anzahl Messwerte', 'Rohdaten-Referenz', 'Zeitraum bis', 'Zeitraum von']});

MATCH (a:KG {id: 'unternehmen:U2', owner: 'provider'}), (b:KG {id: 'drucker:P1', owner: 'provider'}) CREATE (a)-[:BETREIBT]->(b);
MATCH (a:KG {id: 'unternehmen:U2', owner: 'provider'}), (b:KG {id: 'bauteil:000000075612247', owner: 'provider'}) CREATE (a)-[:FERTIGT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'provider'}), (b:KG {id: 'bauteil:000000075612247', owner: 'provider'}) CREATE (a)-[:FUER]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'provider'}), (b:KG {id: 'drucker:P1', owner: 'provider'}) CREATE (a)-[:LAEUFT_AUF]->(b);
MATCH (a:KG {id: 'drucker:P1', owner: 'provider'}), (b:KG {id: 'charge:P1', owner: 'provider'}) CREATE (a)-[:LIEFERT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'provider'}), (b:KG {id: 'charge:P1', owner: 'provider'}) CREATE (a)-[:ERZEUGT]->(b);
MATCH (a:KG {id: 'bauteil:000000075612247', owner: 'provider'}), (b:KG {id: 'dpp:DPP-000000075612247', owner: 'provider'}) CREATE (a)-[:HAT_DPP]->(b);
MATCH (a:KG {id: 'dpp:DPP-000000075612247', owner: 'provider'}), (b:KG {id: 'charge:P1', owner: 'provider'}) CREATE (a)-[:BASIERT_AUF]->(b);

// ===== rheinmetall  (Dataset: WienerNetze) =====
CREATE (:KG:Unternehmen {id: 'unternehmen:U4', owner: 'rheinmetall', kgType: 'Unternehmen', tier: 1, sichtbar: 4, verborgen: 3, stufe: 1, uId: 'U4', name: 'WienerNetze', stadt: 'Wien', land: 'Austria', withheld: ['CO₂ pro kWh', 'Straße', 'Stromtarif (€/kWh)']});
CREATE (:KG:Produktionsauftrag {id: 'auftrag:B-001', owner: 'rheinmetall', kgType: 'Produktionsauftrag', tier: 1, sichtbar: 3, verborgen: 11, stufe: 1, auftragId: 'B-001', materialnummer: '000000075612247', druckmaterial: 'PC-ABS FR', withheld: ['Anzahl Jobs', 'Anzahl Teile', 'Druckzeit gesamt', 'Druckzeit pro Job', 'Druckzeit pro Teil', 'Durchsatz', 'IST-Teile', 'Material (g)', 'Netto-Materialverbrauch pro Job', 'Teile pro Job', 'Teile-Differenz']});
CREATE (:KG:Drucker {id: 'drucker:P1', owner: 'rheinmetall', kgType: 'Drucker', tier: 1, sichtbar: 3, verborgen: 1, stufe: 1, printId: 'P1', herstellerName: 'Stratasys', modell: 'Stratasys_F170', withheld: ['Seriennummer']});
CREATE (:KG:Bauteil {id: 'bauteil:000000075612247', owner: 'rheinmetall', kgType: 'Bauteil', tier: 1, sichtbar: 14, verborgen: 11, stufe: 1, materialnummer: '000000075612247', materialkurztext: 'SchneeschutzgitterØ220mmf.Tyfon,CJ', benennung: 'Schneeschutzgitter Ø 220 für Tyfon', kurztext: 'Schneeschutzgitter', werkstoff: 'X5CrNi18-10 - 1.4301', normBezeichnung: 'EN 10088-3', abmessung: '95XØ202MM', laenge: 0, breite: 0, hoehe: 0, volumen: 0, nettogewicht: 0.25, bruttogewicht: 0.25, gewichtseinheit: 'KG', withheld: ['Bestandsmenge', 'Bestandswert', 'Dokumentnummer', 'Ersteller', 'Ersteller-SachNr', 'Identnummer', 'Lieferant', 'Planlieferzeit (Ø)', 'Preis', 'Sicherheitsbestand (Ø)', 'Zeichnungsnummer (Hersteller)']});
CREATE (:KG:DPP {id: 'dpp:DPP-000000075612247', owner: 'rheinmetall', kgType: 'DPP', tier: 1, sichtbar: 3, verborgen: 7, stufe: 1, materialnummer: '000000075612247', version: 'v1.1', dppId: 'DPP-000000075612247', withheld: ['Anmerkung', 'Bearbeiter', 'CO₂ Herstellung', 'CO₂ in Betrieb', 'Chargen-ID', 'Druckdatum', 'Ereignis/Änderung']});
CREATE (:KG:Fertigungsdaten {id: 'charge:P1', owner: 'rheinmetall', kgType: 'Fertigungsdaten', tier: 1, sichtbar: 2, verborgen: 4, stufe: 1, chargeId: 'CHG-P1', printId: 'P1', withheld: ['Anzahl Messwerte', 'Rohdaten-Referenz', 'Zeitraum bis', 'Zeitraum von']});

MATCH (a:KG {id: 'unternehmen:U4', owner: 'rheinmetall'}), (b:KG {id: 'drucker:P1', owner: 'rheinmetall'}) CREATE (a)-[:BETREIBT]->(b);
MATCH (a:KG {id: 'unternehmen:U4', owner: 'rheinmetall'}), (b:KG {id: 'bauteil:000000075612247', owner: 'rheinmetall'}) CREATE (a)-[:FERTIGT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'rheinmetall'}), (b:KG {id: 'bauteil:000000075612247', owner: 'rheinmetall'}) CREATE (a)-[:FUER]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'rheinmetall'}), (b:KG {id: 'drucker:P1', owner: 'rheinmetall'}) CREATE (a)-[:LAEUFT_AUF]->(b);
MATCH (a:KG {id: 'drucker:P1', owner: 'rheinmetall'}), (b:KG {id: 'charge:P1', owner: 'rheinmetall'}) CREATE (a)-[:LIEFERT]->(b);
MATCH (a:KG {id: 'auftrag:B-001', owner: 'rheinmetall'}), (b:KG {id: 'charge:P1', owner: 'rheinmetall'}) CREATE (a)-[:ERZEUGT]->(b);
MATCH (a:KG {id: 'bauteil:000000075612247', owner: 'rheinmetall'}), (b:KG {id: 'dpp:DPP-000000075612247', owner: 'rheinmetall'}) CREATE (a)-[:HAT_DPP]->(b);
MATCH (a:KG {id: 'dpp:DPP-000000075612247', owner: 'rheinmetall'}), (b:KG {id: 'charge:P1', owner: 'rheinmetall'}) CREATE (a)-[:BASIERT_AUF]->(b);

// ---- nützliche Abfragen (im Neo4j Browser einzeln ausführen) ----
// alles anzeigen:            MATCH (n:KG)-[r]->(m:KG) RETURN n, r, m;
// ein Unternehmen:           MATCH (n:KG {owner:'huber-ag'})-[r]->(m) RETURN n,r,m;
// Bauteile mit Werkstoff:    MATCH (b:Bauteil) RETURN b.owner, b.benennung, b.werkstoff, b.abmessung;
// Herkunftskette eines DPP:  MATCH p=(d:DPP)-[*1..3]-(x:KG) RETURN p;
// was verbirgt dieses Level: MATCH (n:KG) WHERE n.verborgen > 0 RETURN n.owner, n.kgType, n.sichtbar, n.verborgen, n.withheld ORDER BY n.verborgen DESC;
