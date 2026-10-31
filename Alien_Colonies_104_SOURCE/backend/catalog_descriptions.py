"""Short, number-free catalog prose. Effects and balance remain in their own modules.

All text is localized at request time. The fallback keeps future catalog entries
usable until their authored description is added.
"""
try:
    from .i18n import t
except ImportError:
    from i18n import t

SHIP_ROLES = {'scout': 'Zwiadowca',
 'cargo': 'Transportowiec',
 'colonizer': 'Kolonizator',
 'frigate': 'Lekki okręt bojowy',
 'cruiser': 'Ciężki okręt bojowy',
 'interceptor': 'Szybki okręt bojowy',
 'freighter': 'Frachtowiec',
 'siege': 'Okręt oblężniczy',
 'battleship': 'Pancernik',
 'dreadnought': 'Drednot',
 'flagship': 'Okręt specjalny rasy',
 'titan': 'Tytan'}

SHIPS = {'zetans': {'scout': 'Szybki zwiadowca ujawniający zasoby, flotę i obronę planety. Może też odświeżyć właścicieli planet w całym '
                     'układzie.',
            'cargo': 'Szybko przewozi surowce i zwiększa miejsce na łupy. Ma lekki kadłub i słabe uzbrojenie.',
            'colonizer': 'Zakłada kolonie na wolnych planetach lub przejmuje niebronione kolonie graczy poza planetą '
                         'macierzystą. Zużywa się po udanej kolonizacji.',
            'frigate': 'Lekki okręt do pierwszych ataków i eskorty transportów. Szybki, lecz mało wytrzymały.',
            'cruiser': 'Łączy większą siłę ognia i wytrzymałość z dobrą prędkością. Wzmacnia flotę podczas ataków i obrony '
                       'kolonii.',
            'interceptor': 'Bardzo szybki okręt do krótkich wypraw bojowych. Mocniej uderza niż fregata, ale pozostaje podatny '
                           'na straty.',
            'freighter': 'Przewozi duże ilości surowców i łupów, zachowując dobrą prędkość. Słabe uzbrojenie sprawia, że '
                         'potrzebuje eskorty.',
            'siege': 'Ciężki okręt o zwiększonej sile ataku na planety Roju. Jego niewielka prędkość spowalnia wspólną wyprawę.',
            'battleship': 'Silnie uzbrojony pancernik, szybszy od odpowiedników innych ras. Lżejszy kadłub ogranicza jego '
                          'wytrzymałość.',
            'dreadnought': 'Potężna platforma plazmowa do ciężkich bitew. Zadaje duże obrażenia, lecz jest powolna i kosztowna w '
                           'eksploatacji.',
            'flagship': 'Okręt specjalny o wyjątkowo silnej pierwszej salwie. Ta premia wzmacnia wyłącznie jego własny atak.',
            'titan': 'Olbrzymi okręt o potężnej sile ognia i kadłubie, ale bardzo powolny i kosztowny. Wymaga ukończonej Sfery '
                     'Dysona w kolonii budowy.'},
 'symbionts': {'scout': 'Żywy zwiadowca ujawniający zasoby, flotę i obronę planety. Może też odświeżyć właścicieli planet w '
                        'całym układzie.',
               'cargo': 'Pojemny żywy transportowiec przewożący surowce i łupy. Zabiera duży ładunek, ale porusza się powoli i '
                        'słabo walczy.',
               'colonizer': 'Zakłada kolonie na wolnych planetach lub przejmuje niebronione kolonie graczy poza planetą '
                            'macierzystą. Zużywa się po udanej kolonizacji.',
               'frigate': 'Żywy okręt do pierwszych ataków i eskorty. Wytrzymalszy od zetańskiej fregaty, lecz wolniejszy i '
                          'słabiej uzbrojony.',
               'cruiser': 'Wytrzymały żywy okręt do cięższych bitew. Regeneruje uszkodzenia ocalałych kadłubów między rundami '
                          'walki.',
               'interceptor': 'Szybki żywy okręt do najazdów. Łączy większą mobilność od ciężkiej floty z kadłubem mocniejszym '
                              'niż zetański odpowiednik.',
               'freighter': 'Żywy frachtowiec o wyjątkowo dużej ładowni na surowce i łupy. Jest powolny i potrzebuje eskorty '
                            'bojowej.',
               'siege': 'Wytrzymały żywy okręt o zwiększonej sile ataku na planety Roju. Porusza się wolno i korzysta z '
                        'regeneracji ocalałych kadłubów.',
               'battleship': 'Pancernik o grubym żywym kadłubie, przystosowany do dłuższych starć. Regeneruje uszkodzenia '
                             'ocalałych jednostek między rundami.',
               'dreadnought': 'Ogromny organizm bojowy łączący silny atak z dużą wytrzymałością. Jest powolny, lecz potrafi '
                              'regenerować uszkodzenia w walce.',
               'flagship': 'Okręt specjalny z silniejszą regeneracją własnych ocalałych kadłubów. Nie odtwarza zniszczonych '
                           'jednostek ani nie leczy innych typów okrętów.',
               'titan': 'Tytaniczny organizm o ogromnej wytrzymałości i sile ataku, ale bardzo powolny i kosztowny. Wymaga '
                        'ukończonej Sfery Dysona w kolonii hodowli.'},
 'automatons': {'scout': 'Opancerzona sonda ujawniająca zasoby, flotę i obronę planety. Może też odświeżyć właścicieli planet w '
                         'całym układzie.',
                'cargo': 'Opancerzony transportowiec przewożący surowce i łupy. Jest wytrzymały jak na statek transportowy, ale '
                         'powolny i paliwożerny.',
                'colonizer': 'Zakłada kolonie na wolnych planetach lub przejmuje niebronione kolonie graczy poza planetą '
                             'macierzystą. Zużywa się po udanej kolonizacji.',
                'frigate': 'Podstawowy okręt bojowy do ataku i eskorty. Mocny kadłub okupuje niższą prędkością i większym '
                           'zużyciem paliwa.',
                'cruiser': 'Ciężki okręt o dużej wytrzymałości i sile ognia. Dobrze znosi ostrzał, lecz porusza się wolno i '
                           'zużywa dużo paliwa.',
                'interceptor': 'Szybki okręt uderzeniowy z mocnym kadłubem. Nadaje się do najazdów, ale zużywa więcej paliwa niż '
                               'odpowiedniki innych ras.',
                'freighter': 'Opancerzony frachtowiec do przewozu dużych zapasów i łupów. Jest powolny, paliwożerny i wymaga '
                             'eskorty w walce.',
                'siege': 'Ciężki okręt o zwiększonej sile ataku na planety Roju. Ma bardzo mocny kadłub, lecz jest powolny i '
                         'paliwożerny.',
                'battleship': 'Pancernik łączący dużą siłę ognia z mocnym kadłubem. Wysoka wytrzymałość okupiona jest '
                              'powolnością i zużyciem paliwa.',
                'dreadnought': 'Ciężki drednot o potężnej sile ognia i pancerzu. Wymaga dużych zapasów paliwa i spowalnia '
                               'towarzyszącą mu flotę.',
                'flagship': 'Okręt specjalny z dodatkową redukcją otrzymywanych obrażeń. Wzmocniony pancerz chroni wyłącznie '
                            'jego własne jednostki.',
                'titan': 'Najcięższy okręt maszyn, z olbrzymim kadłubem i potężnymi działami, ale bardzo powolny i paliwożerny. '
                         'Wymaga ukończonej Sfery Dysona w kolonii budowy.'},
 'neutral': {'scout': 'Ujawnia zasoby, flotę i obronę wybranej planety. Może też odświeżyć właścicieli planet w całym układzie.',
             'cargo': 'Przewozi surowce między koloniami i zwiększa miejsce na łupy. Słabo uzbrojony, potrzebuje eskorty podczas '
                      'ataków.',
             'colonizer': 'Zakłada kolonie na wolnych planetach lub przejmuje niebronione kolonie graczy poza planetą '
                          'macierzystą. Zużywa się po udanej kolonizacji.',
             'frigate': 'Lekki okręt do pierwszych ataków, obrony kolonii i eskorty transportów. Jest szybszy i tańszy od '
                        'ciężkich jednostek.',
             'cruiser': 'Cięższy okręt o większej sile ognia i wytrzymałości niż fregata. Lepiej znosi walkę kosztem prędkości i '
                        'paliwa.',
             'interceptor': 'Szybki okręt do krótkich wypraw bojowych. Łączy silniejszy atak niż fregata z większą prędkością.',
             'freighter': 'Przewozi znacznie więcej surowców i łupów niż zwykły transportowiec. Duża ładownia idzie w parze z '
                          'niską prędkością i słabym uzbrojeniem.',
             'siege': 'Ciężki okręt o zwiększonej sile ataku na planety Roju. Niewielka prędkość wydłuża podróż całej floty.',
             'battleship': 'Silnie uzbrojony okręt do ciężkich bitew, mocniejszy od krążownika. Jego szczególne cechy zależą od '
                           'wybranej rasy.',
             'dreadnought': 'Ciężki okręt o potężnej sile ognia i wytrzymałości. Jest powolny, kosztowny i wymaga dużych zapasów '
                            'paliwa.',
             'flagship': 'Specjalny okręt rasy z wyjątkowo silną salwą, regeneracją lub pancerzem. Jego premia dotyczy wyłącznie '
                         'jednostek tego typu.',
             'titan': 'Potężny okręt końcowego etapu rozwoju, bardzo powolny i kosztowny. Wymaga ukończonej Sfery Dysona w '
                      'kolonii budowy.'},
 'swarm': {'scout': 'Mały i szybki organizm Roju o bardzo słabym kadłubie i uzbrojeniu.',
           'cargo': 'Organizm transportowy zwiększający miejsce na zasoby zdobywane przez Rój. Ma pojemną ładownię i niewielką '
                    'siłę ataku.',
           'colonizer': 'Zakłada nowe gniazdo Roju na wolnej planecie. Zostaje zużyty podczas zasiedlenia.',
           'frigate': 'Lekki organizm bojowy tworzący podstawę chmary. Pojedynczo słaby, staje się groźny w dużej liczbie.',
           'cruiser': 'Ciężki organizm bojowy o znacznie większej sile ataku i wytrzymałości niż Żuwacz. Jest wolniejszy i '
                      'zużywa więcej paliwa.'}}

RESEARCH = {'propulsion': 'Przyspiesza podróże całej floty poza tunelami czasoprzestrzennymi.',
 'weapons': 'Zwiększa siłę ataku statków i obrony planetarnej.',
 'energy_technology': 'Zwiększa produkcję energii przez elektrownie.',
 'computing': 'Skraca czas prowadzenia badań w całym imperium.',
 'fusion_power': 'Zwiększa produkcję energii przez elektrownie.',
 'robotics': 'Skraca czas budowy i ulepszania budynków.',
 'superconductors': 'Zmniejsza zapotrzebowanie kopalń i rafinerii na energię.',
 'nanotechnology': 'Wydobycie +3% na poziom. Co 3 poziomy skraca o połowę czas budowy budynków, statków i obrony.',
 'hyperspace': 'Przyspiesza loty floty poza tunelami i otwiera drogę do zaawansowanych okrętów.',
 'stellar_collectors': 'Zwiększa produkcję energii przez elektrownie i otwiera drogę do inżynierii gwiezdnej.',
 'orbital_engineering': 'Skraca czas budowy statków i obrony planetarnej.',
 'graviton_control': 'Zmniejsza zużycie paliwa przez silniki podczas lotów.',
 'stellar_engineering': 'Zwiększa moc Sfery Dysona i przyspiesza ładowanie jej magazynu energii.',
 'megastructures': 'Przyspiesza budowę megastruktur i powiększa magazyn energii Sfery Dysona.',
 'spacetime_stability': 'Zmniejsza zużycie energii przy otwieraniu, podtrzymywaniu i używaniu tuneli czasoprzestrzennych.',
 'dyson_design': 'Odblokowuje budowę Sfery Dysona, która dostarcza i magazynuje energię.',
 'wormhole_theory': 'Odblokowuje tunel czasoprzestrzenny przy ukończonej Sferze Dysona, umożliwiając szybkie podróże floty.',
 'capital_shipbuilding': 'Pozwala odblokować ciężkie okręty i skraca budowę statków oraz obrony planetarnej.',
 'capital_weapons': 'Zwiększa siłę ataku pancerników, drednotów, okrętów specjalnych i tytanów.',
 'titan_core': 'Odblokowuje tytany i znacznie powiększa magazyn energii Sfery Dysona.',
 'antigravity': 'Dodatkowo przyspiesza loty całej floty poza tunelami czasoprzestrzennymi.',
 'phase_hulls': 'Zwiększa wytrzymałość statków i obrony planetarnej oraz pozwala odblokować okręty przechwytujące.',
 'coherent_plasma': 'Zwiększa siłę ataku statków i obrony planetarnej oraz pozwala odblokować okręty oblężnicze.',
 'folding_cargo': 'Powiększa ładownie wszystkich statków i pozwala odblokować ciężkie transportowce.',
 'psionic_command': 'Odblokowuje Pryzmat Osobliwości, okręt specjalny o wyjątkowo silnej pierwszej salwie.',
 'multiplication': 'Pomnaża posiadaną flotę, również w podróży, i zwiększa liczbę statków uzyskiwanych z hodowli.',
 'chitin_layers': 'Zwiększa wytrzymałość statków i obrony planetarnej oraz pozwala odblokować okręty przechwytujące.',
 'corrosive_spores': 'Zwiększa siłę ataku statków i obrony planetarnej oraz pozwala odblokować okręty oblężnicze.',
 'metabolic_drive': 'Zmniejsza zużycie paliwa przez silniki i pozwala odblokować ciężkie transportowce.',
 'brood_sovereignty': 'Odblokowuje Matriarchę, okręt specjalny regenerujący własny kadłub podczas walki.',
 'recycling': 'Zwraca część surowców po ukończeniu budynków, ulepszeń, statków i obrony planetarnej.',
 'composite_armor': 'Zwiększa wytrzymałość statków i obrony planetarnej oraz pozwala odblokować okręty przechwytujące.',
 'siege_algorithms': 'Zwiększa siłę ataku statków i obrony planetarnej oraz pozwala odblokować okręty oblężnicze.',
 'modular_cargo': 'Powiększa ładownie wszystkich statków i pozwala odblokować ciężkie transportowce.',
 'siege_autonomy': 'Odblokowuje Bastion Omega, okręt specjalny z dodatkową ochroną przed obrażeniami.'}

def brief_description(group, key, race_id="", fallback=""):
    if group == "ships":
        source = SHIPS.get(race_id or "neutral", {}).get(key)
        if source is None:
            source = SHIPS["neutral"].get(key)
    elif group == "research":
        source = RESEARCH.get(key)
    else:
        return fallback
    return t(source) if source else fallback
