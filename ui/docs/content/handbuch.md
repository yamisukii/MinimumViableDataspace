# Anwenderhandbuch

Sieben Unternehmen tauschen Bauteil-, Prozess- und Qualitätsdaten aus — und jedes
entscheidet selbst, wer davon was sehen darf. Diese Anleitung zeigt, wie Sie das
im Portal tun. Technische Vorkenntnisse sind nicht nötig.

## Die Idee in drei Sätzen

Wer Bauteile fertigen lässt, muss Daten herausgeben: Geometrie, Werkstoff,
Prozessparameter, Prüfergebnisse. Genau das will niemand ungefiltert tun — eine
technische Zeichnung geht den Auftragsfertiger etwas an, den Wettbewerb nicht.

Der Datenraum löst das, indem die Daten **bei ihrem Eigentümer bleiben**. Nichts
wird in eine zentrale Plattform hochgeladen. Stattdessen veröffentlicht jedes
Unternehmen einen Katalog, und wer etwas daraus möchte, schließt automatisiert
einen Vertrag ab. Erst danach fließt die Datei — direkt von A nach B.

Zwei Fragen entscheiden jeden Zugriff: **Wie nah steht mir dieses Unternehmen?**
und **Welche Rolle hat die Person dort?** Aus beiden ergibt sich, was sichtbar ist.

## Anmelden

Das Portal läuft unter `http://127.0.0.1:5180`. Angemeldet wird sich als *Person*,
nicht als Firma — jede Person gehört zu genau einem Unternehmen.

Für den Einstieg gibt es je Unternehmen ein Konto, das den Firmennamen trägt und
automatisch **Leiter** ist. Das Passwort ist überall `password`.

| Benutzer | Unternehmen | Rolle im Konzern |
|---|---|---|
| `wiener-stadtwerke` | Wiener Stadtwerke | Holding |
| `wiener-linien` | Wiener Linien | Tochter |
| `wien-energie` | Wien Energie | Tochter |
| `wiener-netze` | Wiener Netze | Tochter |
| `oebb` | ÖBB | eigener Konzern |
| `fha-wien` | Fraunhofer Austria Wien | Forschung |
| `fha-tirol` | Fraunhofer Austria Tirol | Forschung |

### Leiter oder Arbeiter

Es gibt zwei Rollen, und sie steuern, wie viel eine Person vom Erlaubten
tatsächlich sieht:

- **Leiter** — sieht alles, was das eigene Unternehmen sehen darf. Nur Leiter
  haben den Reiter *Verwaltung* und dürfen Personen anlegen und andere Firmen
  einstufen.
- **Arbeiter** — sieht alles außer **T3**, also keine CAD-Dateien und keine
  technischen Zeichnungen, selbst bei einer Tochtergesellschaft.

Weitere Personen legt ein Leiter unter *Verwaltung* an. Sinnvoll sind Namen wie
`fha-wien-worker1`, damit die Zugehörigkeit erkennbar bleibt.

## Wer mitmacht

Sieben Teilnehmer in drei Gruppen. Jeder ist technisch vollwertig — eigene
Identität, eigener Katalog, eigene Dateiablage. Was sie unterscheidet, ist die
Menge an Daten, die sie mitbringen.

| Unternehmen | Bringt mit | Angebote |
|---|---|---|
| **Fraunhofer Austria Wien** | Der datenreichste Teilnehmer: drei Drucker, komplette Fertigungskette mit Bauteilen, Chargen und Qualitätsprüfungen. Hier liegen auch die CAD-Dateien. | 8 |
| **Fraunhofer Austria Tirol** | Ein Drucker, Druckprofile, Aufträge. Zu Wien konzernintern verbunden. | 2 |
| **ÖBB** | Stammdaten einer Adapterplatte, dazu ein gerichteter Qualitätsbericht und drei technische Demo-Assets. | 6 |
| **Wiener Linien** | Stammdaten eines Gehäusedeckels. | 2 |
| **Wien Energie**, **Wiener Netze**, **Wiener Stadtwerke** | Treten als Datenbezieher auf. Sie haben je nur ein Demo-Angebot und erscheinen nicht in der Suche — der Datensatz enthält für sie keine Bauteile. | 1 |

Für eine Vorführung ist **Fraunhofer Austria Wien** der beste Startpunkt: dort ist
am meisten zu sehen, und von dort lassen sich alle Effekte zeigen.

## Die sechs Reiter

Nach der Anmeldung gliedert sich das Portal in sechs Bereiche.

- **Dataspace** — Alle anderen Teilnehmer. Ein Klick auf ein Unternehmen öffnet
  dessen Katalog; von dort wird bezogen.
- **Suche** — Semantische Suche über alle Teilnehmer plus Filter nach Werkstoff,
  Drucker, Abmaßen. Der Weg, wenn Sie nicht wissen, wer etwas hat.
- **Meine Assets** — Eigene Dateien anbieten und die eigenen Angebote überblicken.
- **Eingehende Berichte** — Qualitätsberichte, die andere gezielt an Sie gerichtet
  haben. Niemand sonst sieht sie.
- **Meine Dateien** — Empfangene und hochgeladene Dateien. Zu empfangenen
  Bauteilen lässt sich ein Bericht zurücksenden.
- **Verwaltung** *(nur Leiter)* — Personen anlegen und andere Unternehmen
  einstufen. Hier stellen Sie ein, wer wie viel von Ihnen sieht.

## Wer darf was sehen

Das ist der Kern des Datenraums. Jede angebotene Datei trägt eine
**Vertraulichkeitsstufe**, und jedes andere Unternehmen hat bei Ihnen eine
**Beziehungsstufe**. Sichtbar ist, was beides zulässt.

### Die drei Vertraulichkeitsstufen

| Stufe | Inhalt | Beispiel aus der Demo |
|---|---|---|
| **T1** | Stammdaten — Benennung, Werkstoff, Abmaße, Gewicht | Stammdaten Adapterplatte |
| **T2** | Prozess und Bestand — Druckparameter, Lagermengen, Preise, Lieferanten | Prozessparameter Charge 7 |
| **T3** | CAD und Qualitätsdaten — Geometrie, technische Zeichnungen, Prüfprotokolle | CAD Halterung V2 |

### Die drei Beziehungsstufen

Jedes Unternehmen stuft die anderen selbst ein — und zwar einseitig. Sie können
ÖBB als Partner führen, während ÖBB Sie als fremd führt. Beide Sichten sind
unabhängig.

| Beziehung | Bedeutung | T1 | T2 | T3 |
|---|---|---|---|---|
| **fremd** | Kein besonderes Verhältnis | ja | — | — |
| **Partner** | Geschäftsbeziehung, Kooperation | ja | ja | — |
| **Tochter** | Konzernintern, gleiche Organisation | ja | ja | ja |

### Beide Bedingungen gelten gleichzeitig

Die Personenrolle begrenzt zusätzlich: Ein **Arbeiter** bekommt nie T3, auch nicht
in einer Tochtergesellschaft. Es gilt also immer die *strengere* der beiden
Bedingungen.

> **So sieht das konkret aus.** Fraunhofer Austria Wien bietet 8 Dateien an. ÖBB
> ist dort als **Partner** eingestuft und sieht deshalb nur **6** — die beiden
> T3-Dateien (CAD Halterung V2 und der Aluminium-Würfel) erscheinen gar nicht im
> Katalog. Melden Sie sich als `oebb` an und vergleichen Sie mit der Sicht von
> `fha-tirol`, das konzernintern verbunden ist.

### Auffindbar ist nicht gleich zugänglich

In der Suche kann ein Treffer erscheinen, den Sie nicht beziehen dürfen. Das ist
Absicht: Sie erfahren, *dass* es das Teil gibt, und können nachfragen. Einzelne
Angaben sind dann als **verborgen** markiert, und der Bezug wird abgelehnt.

## Daten finden

Es gibt zwei Wege, und sie beantworten verschiedene Fragen.

### Suche — „wofür ist das Teil?"

Im Reiter *Suche* beschreiben Sie in eigenen Worten, was Sie brauchen. Gesucht
wird über Freitext: Einsatzzweck, Funktion, Anforderungen, Synonyme. Sie müssen
den Namen des Bauteils nicht kennen.

```
abdeckung für schaltschrank
montageadapter lochbild
werbeartikel messe
```

Jeder Treffer zeigt seine Ähnlichkeit zur Anfrage, das anbietende Unternehmen und
die Angaben, die Sie sehen dürfen.

### Filter — „welche Eigenschaften?"

Unter dem Suchfeld erscheinen Filter für Werkstoff, Drucker, Druckermodell,
Branche und Standort sowie Zahlenfelder für Länge, Breite, Höhe und Gewicht. Diese
Angaben gehören bewusst *nicht* in die Freitextsuche — „maximal 5 cm" lässt sich
sprachlich nicht zuverlässig treffen, als Filter dagegen exakt.

Nützlich ist die Kombination: erst sprachlich eingrenzen, dann über die Filter auf
einen Werkstoff oder eine Maschine verengen.

### Im Knowledge Graph nachsehen

Über *Im KG anzeigen* öffnet sich die Umgebung eines Treffers als Graph: welches
Unternehmen das Teil führt, auf welchem Drucker es läuft, aus welchem Auftrag es
kommt, welche Prüfung es durchlaufen hat. Auch dieser Graph ist auf Ihre Stufe
beschnitten — Knoten und einzelne Angaben oberhalb Ihrer Berechtigung fehlen
beziehungsweise erscheinen als verborgen.

> **Reindex.** Nach einem Upload erscheint die Datei sofort im Katalog. Sollte sie
> in der Suche fehlen, hilft der Knopf *Reindex* im Reiter *Suche*: er meldet die
> eigenen Angebote neu an.

## Daten beziehen

Wählen Sie im Reiter *Dataspace* ein Unternehmen, dann im Katalog ein Angebot und
klicken *Beziehen*. Aus der Suche heraus geht es genauso. Danach laufen fünf
Schritte ab, die das Portal mitzeichnet — die Reihenfolge ist fest, weil jeder
Schritt auf dem vorigen aufbaut.

1. **Contract Negotiation starten** — Ihr Connector fragt beim Anbieter die
   Nutzungsbedingungen an und legt seine Nachweise vor.
2. **Auf Agreement warten** — Der Anbieter prüft die Nachweise und bestätigt den
   Vertrag. Fehlt eine Berechtigung, endet es hier mit einer Ablehnung.
3. **Transfer starten** — Auf Basis des Vertrags wird die Übertragung angemeldet.
4. **Auf Freigabe warten** — Der Anbieter stellt einen befristeten Zugang zur
   Datei aus, der nur für diesen Vorgang gilt.
5. **Daten herunterladen und speichern** — Die Datei wird geholt und in Ihrer
   Ablage gesichert.

Das Ergebnis finden Sie unter *Meine Dateien* → *Empfangene Dateien*. Zu jeder
Datei wird festgehalten, von wem sie stammt, aus welchem Angebot und wann sie
eintraf. Diese Herkunft bleibt an der Datei hängen — sie ist die Grundlage dafür,
später einen Bericht an den richtigen Anbieter zurückzusenden.

Im Dateisystem liegen die Dateien unter
`compose/companies/<unternehmen>/storage/downloads` und sind dort auch im Explorer
sichtbar.

> **Gut zu wissen.** Ein eigenes Angebot müssen Sie nicht beziehen — dort steht
> statt des Knopfes ein Hinweis. Und der Vorgang bricht sauber ab, wenn eine
> Berechtigung fehlt; es entsteht keine halbe Datei.

## Eigene Daten anbieten

Im Reiter *Meine Assets* laden Sie unter *Neues Datenprodukt anbieten* eine Datei
hoch. Übliche Formate sind STL, STEP und 3MF, es geht aber jedes Format.

| Feld | Wozu |
|---|---|
| **Datei** *(Pflicht)* | Die Datei selbst |
| **Bauteil-Name** *(Pflicht)* | Woran andere das Teil erkennen, z. B. „Halterung V2" |
| Materialkurztext | Interne Bezeichnung, falls vorhanden |
| Werkstoff | z. B. `1.4404` oder `AlSi10Mg` — wird als Filter nutzbar |
| Abmaße (L×B×H) | z. B. `20x20x5 mm` — ebenfalls filterbar |
| Verfahren | z. B. `LPBF` oder `SLM` |
| Beschreibung | Ein Satz zum Zweck. Zahlt sich aus, weil die Suche darüber findet. |
| **Vertraulichkeit** | Die entscheidende Wahl — siehe unten |

### Die Stufe richtig wählen

- **T1** Stammdaten — auch für Fremde sichtbar. Für alles, was ein Katalogeintrag
  ohnehin verrät.
- **T2** Prozess und Bestand — nur Partner und Töchter. Für Druckparameter,
  Mengen, Preise.
- **T3** CAD und technische Zeichnung — nur Töchter, und dort nur Leiter. Für
  alles, woraus sich das Teil nachbauen lässt.

Die Stufe wirkt sofort und lässt sich nicht nachträglich im Portal ändern — im
Zweifel höher einstufen. Nach dem Hochladen ist die Datei unmittelbar im Katalog
der Berechtigten sichtbar und über die Suche findbar.

## Qualitätsbericht senden

Haben Sie ein Bauteil bezogen und geprüft, können Sie das Ergebnis **gezielt an
den ursprünglichen Anbieter** zurückgeben — nicht per Mail, sondern über denselben
kontrollierten Weg wie den Bezug.

Gehen Sie auf *Meine Dateien*, suchen die empfangene Datei und klicken
*Qualitätsbericht senden*. Das Ziel ist dadurch festgelegt: es ist der Anbieter,
von dem die Datei stammt.

| Feld | Wozu |
|---|---|
| **Berichtsdatei** *(Pflicht)* | Ihr Protokoll, etwa als PDF oder CSV |
| **Titel** *(Pflicht)* | z. B. „Prüfbericht Halterung V2" |
| Ergebnis | bestanden · mit Auflagen · nicht bestanden |
| Anmerkungen | Kurzbefund, z. B. „Maßhaltigkeit i. O., Oberfläche geprüft" |

Der Bericht wird als Angebot angelegt, das **ausschließlich für das
Zielunternehmen** existiert. Andere Teilnehmer sehen ihn nicht einmal im Katalog.
Der Empfänger findet ihn unter *Eingehende Berichte* und bezieht ihn wie jede
andere Datei.

> **Zum Vorführen.** In der Demo liegt bei ÖBB bereits ein Bericht für Fraunhofer
> Austria Wien. Öffnen Sie den ÖBB-Katalog als `fha-wien` — der Bericht ist da.
> Dann als `wiener-linien` oder `fha-tirol`: derselbe Katalog, ein Eintrag weniger.

## Zugriff verwalten

Der Reiter *Verwaltung* steht nur Leitern offen und hat zwei Hälften.

### Personen im Unternehmen

Hier legen Sie Kolleginnen und Kollegen an: Benutzername, Passwort und Rolle
(**Leiter** oder **Arbeiter**). Die Person gehört automatisch zu Ihrem
Unternehmen. So zeigen Sie den Unterschied, ohne die Firmenbeziehung anzufassen:
Ein Arbeiter bei Fraunhofer Austria Wien sieht die eigenen CAD-Dateien nicht.

### Andere Unternehmen einstufen

Hier setzen Sie je Unternehmen **fremd**, **Partner** oder **Tochter**. Die
Änderung wirkt sofort — im Katalog, in der Suche und beim Bezug.

Wichtig: Sie regeln damit nur, *was andere von Ihnen sehen*. Was Sie bei anderen
sehen, entscheiden die jeweils selbst.

### Wie die Demo eingestellt ist

| Beziehung | Stufe |
|---|---|
| Wiener Stadtwerke ↔ Linien, Energie, Netze — und die Schwestern untereinander | **Tochter** |
| Fraunhofer Austria Wien ↔ Fraunhofer Austria Tirol | **Tochter** |
| alle übrigen Paare (Forschung ↔ Konzerne, ÖBB ↔ Stadtwerke-Gruppe) | **Partner** |

> **Vor einer Vorführung beachten.** Damit steht derzeit **kein Paar auf „fremd"**.
> Der stärkste Effekt — ein Fremder sieht ausschließlich T1 — ist deshalb nicht
> ohne Weiteres zu zeigen. Stufen Sie dafür kurz ein Unternehmen unter
> *Verwaltung* auf *fremd* herab und öffnen dessen Sicht auf Ihren Katalog. Das
> ist ein Klick und sofort rückgängig zu machen.

## Unternehmen aufnehmen

Ein neuer Teilnehmer wird über eine eigene Oberfläche angelegt. Starten Sie sie mit

```powershell
compose\start-onboarding.ps1
```

und öffnen `http://127.0.0.1:5175`. Dort tragen Sie Name, Anzeigename und
Beschreibung ein; der Rest läuft selbst: Schlüsselpaar, Identität, Nachweise,
Katalog. Nach ein bis zwei Minuten ist das Unternehmen voll teilnahmefähig und
erscheint bei allen anderen im Reiter *Dataspace*. Die Oberfläche zeigt den
Fortschritt mit und erlaubt auch, einen Teilnehmer wieder zu entfernen.

Für den Namen gilt: Kleinbuchstaben, Ziffern und Bindestriche, beginnend mit einem
Buchstaben, etwa `mueller-gmbh`. Er taucht später in Adressen auf und lässt sich
nicht mehr ändern.

Nach dem Anlegen melden Sie sich einmal mit dem Firmennamen und `password` an —
damit entsteht das Leiter-Konto. Anschließend die anderen Unternehmen einstufen,
sonst bleibt der neue Teilnehmer für alle „fremd".

## Starten und stoppen

Alles zusammen startet ein Befehl im Projektordner:

```powershell
.\start.ps1
```

Das fährt die Container hoch und öffnet weitere Fenster für Suche, Portal und
Dokumentation. Der Aufruf ist wiederholbar — nach einem Rechnerneustart einfach
erneut ausführen. Alle Daten bleiben erhalten: Angebote, Verträge, Identitäten,
empfangene Dateien.

| Dienst | Adresse | Wofür |
|---|---|---|
| Portal | `127.0.0.1:5180` | Die Hauptoberfläche |
| Suche | `127.0.0.1:5185` | Läuft im Hintergrund, wird vom Portal benötigt |
| Dokumentation | `127.0.0.1:5190` | Diese Anleitung und die technischen Dokus |
| Onboarding | `127.0.0.1:5175` | Nur zum Anlegen neuer Unternehmen |

Die Hintergrundfenster gehören dazu: **Wird ein Fenster geschlossen, ist der
Dienst weg.** Das Portal meldet dann Fehler bei der Suche. Einzeln nachstarten
lassen sie sich mit `compose\start-discovery.ps1`, `compose\start-portal.ps1` und
`compose\start-docs.ps1`.

Zum Beenden genügt es, die Fenster zu schließen. Die Container laufen weiter und
werden beim nächsten `.\start.ps1` wiederverwendet.

## Wenn etwas nicht geht

### Das Portal lädt nicht

Prüfen, ob das Portal-Fenster noch offen ist. Wenn nicht:
`compose\start-portal.ps1`.

### Die Suche liefert nichts oder meldet einen Fehler

Der Suchdienst auf Port 5185 läuft nicht. Mit `compose\start-discovery.ps1`
starten — der erste Start dauert einen Moment, weil das Sprachmodell geladen wird.
Findet die Suche danach eigene Dateien nicht, im Reiter *Suche* auf *Reindex*
klicken.

### Anmeldung schlägt fehl

Benutzername kleingeschrieben und genau wie in der Tabelle? Standardpasswort ist
`password`. Bei selbst angelegten Personen gilt das Passwort, das der Leiter
gesetzt hat.

### Ein Bezug bricht ab oder wird abgelehnt

Meist fehlt die Berechtigung: Die Datei liegt über Ihrer Stufe bei diesem
Anbieter, oder Sie sind als Arbeiter angemeldet und es ist eine T3-Datei. Der
Anbieter kann Sie unter *Verwaltung* höher einstufen. Bricht es bei Schritt 4 mit
einer Zeitüberschreitung ab, war der Anbieter kurz nicht erreichbar — einfach
erneut versuchen.

### Ein Unternehmen fehlt im Dataspace

Nach dem Onboarding dauert es ein bis zwei Minuten, bis alle Nachweise ausgestellt
sind. Seite neu laden.

### Nichts läuft mehr

`.\start.ps1` erneut ausführen; der Aufruf ist gefahrlos wiederholbar. Bleibt es
beim Start hängen, ist meist die Container-Umgebung nicht gestartet — dann hilft
in aller Regel `wsl --shutdown` und ein erneuter Versuch.

## Grenzen dieser Demo

Damit in einer Vorführung nichts überrascht — was dieser Aufbau bewusst noch nicht
leistet:

- **Die Beschreibungen der Bauteile sind Platzhalter.** Der zugrundeliegende
  Datensatz enthält keine Freitextfelder, die erklären, wofür ein Teil da ist. Die
  Texte wurden aus Bauteilname und Werkstoff abgeleitet. Die Suche funktioniert
  damit, aber echte Beschreibungen würden sie deutlich verbessern.
- **Drei Teilnehmer haben keine Bauteildaten.** Wien Energie, Wiener Netze und die
  Holding erscheinen nicht in der Suche — der Datensatz kennt nur vier Materialien
  und Drucker an zwei Standorten.
- **Kein Paar ist auf „fremd" gesetzt.** Für den Kontrast muss eine Stufe kurz
  herabgesetzt werden.
- **Alle Passwörter sind Demo-Werte.** Durchgehend `password`. Nichts davon ist
  für einen Betrieb außerhalb dieses Rechners geeignet.
- **Zwei Werte im Datensatz sind auffällig falsch:** beim ABS-Schlüsselanhänger
  steht eine Norm für Edelstahl, und als Hersteller „Musterfirma". Das kommt aus
  der Quelldatei.
- **Portal, Suche und Dokumentation laufen als Fenster auf dem Rechner**, nicht
  als Dienste. Für einen Server-Betrieb müssten sie noch verpackt werden.

> **Wichtig.** Die Zugriffssteuerung ist echt und wird an zwei Stellen unabhängig
> durchgesetzt — die Oberfläche filtert, und die Connectoren prüfen zusätzlich
> kryptografische Nachweise. Ein Katalog zeigt also nicht deshalb weniger, weil
> etwas ausgeblendet wäre: die Daten werden gar nicht herausgegeben.
