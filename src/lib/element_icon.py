import pathlib
from types import MappingProxyType

from src.models.db.element import Element
from src.models.element_type import ElementType

_CONFIG = MappingProxyType(
    {
        'aeroway': {
            'aerodrome': 'aeroway_airport.webp',
            'gate': 'aeroway_gate.webp',
            'helipad': 'aeroway_helipad.webp',
            'terminal': 'aeroway_terminal.webp',
            'parking_position': 'aeroway_gate.webp',
            ElementType.way: {
                'runway': 'aeroway_runway.20.webp',
                'taxiway': 'aeroway_taxiway.20.webp',
            },
        },
        'amenity': {
            'atm': 'amenity_atm.16.webp',
            'bank': 'amenity_bank.16.webp',
            'bar': 'amenity_bar.16.webp',
            'bench': 'amenity_bench.16.webp',
            'biergarten': 'amenity_biergarten.16.webp',
            'bicycle_parking': 'amenity_bicycle_parking.webp',
            'bicycle_rental': 'amenity_bicycle_rental.webp',
            'bureau_de_change': 'amenity_bureau_de_change.webp',
            'bus_station': 'amenity_bus_station.16.webp',
            'cafe': 'amenity_cafe.16.webp',
            'car_rental': 'amenity_car_rental.webp',
            'car_sharing': 'amenity_car_sharing.webp',
            # TODO: 'car_wash': '',
            'casino': 'amenity_casino.webp',
            # TODO: 'charging_station': '',
            'childcare': 'amenity_nursery.webp',
            'cinema': 'amenity_cinema.16.webp',
            'clinic': 'amenity_doctors.webp',
            'clock': 'amenity_clock.webp',
            'college': 'amenity_college.webp',
            'courthouse': 'amenity_courthouse.16.webp',
            'dentist': 'amenity_dentist.16.webp',
            'doctors': 'amenity_doctors.16.webp',
            'drinking_water': 'amenity_drinking_water.16.webp',
            'fast_food': 'amenity_fast_food.16.webp',
            'fire_station': 'amenity_fire_station.16.webp',
            'fountain': 'amenity_fountain.webp',
            'fuel': 'amenity_fuel.16.webp',
            'grave_yard': 'historic_memorial.16.webp',
            'hospital': 'amenity_hospital.16.webp',
            'hunting_stand': 'man_made_lookout_tower.webp',
            'ice_cream': 'amenity_ice_cream.webp',
            'kindergarten': 'amenity_school.webp',
            'library': 'library.16.webp',
            'luggage_locker': 'amenity_luggage_locker.webp',
            'marketplace': 'amenity_marketplace.webp',
            'nightclub': 'amenity_nightclub.16.webp',
            'parking': 'amenity_parking.webp',
            # TODO: 'parking_entrance': '',
            # TODO: 'parking_space': '',
            'pharmacy': 'amenity_pharmacy.16.webp',
            'photo_booth': 'amenity_photo_booth.webp',
            'place_of_worship': 'amenity_place_of_worship.16.webp',
            'police': 'amenity_police.16.webp',
            'post_box': 'post_box.16.webp',
            'post_office': 'post_office.16.webp',
            'prison': 'amenity_prison.16.webp',
            'pub': 'amenity_pub.16.webp',
            'public_building': 'amenity_public_building.webp',
            'recycling': 'amenity_recycling.16.webp',
            'restaurant': 'amenity_restaurant.16.webp',
            'school': 'amenity_school.webp',
            'shelter': 'amenity_shelter.16.webp',
            'stripclub': 'amenity_nightclub.16.webp',
            'taxi': 'amenity_taxi.16.webp',
            'telephone': 'telephone.16.webp',
            'theatre': 'amenity_theatre.16.webp',
            'toilets': 'amenity_toilets.16.webp',
            'townhall': 'amenity_townhall.16.webp',
            'university': 'amenity_university.webp',
            'vending_machine': 'amenity_vending_machine.webp',
            'veterinary': 'amenity_veterinary.webp',
            'waste_basket': 'amenity_waste_basket.16.webp',
            'water_point': 'amenity_drinking_water.16.webp',
        },
        'barrier': {
            'block': 'barrier_block.webp',
            'bollard': 'barrier_bollard.webp',
            'cattle_grid': 'barrier_cattle_grid.webp',
            'cycle_barrier': 'barrier_cycle_barrier.webp',
            'entrance': 'barrier_entrance.webp',
            'gate': 'barrier_gate.16.webp',
            # TODO: 'kerb': '',
            'kissing_gate': 'barrier_kissing_gate.webp',
            'lift_gate': 'barrier_lift_gate.webp',
            'stile': 'barrier_stile.webp',
            'toll_booth': 'barrier_toll_booth.webp',
            'turnstile': 'barrier_turnstile.webp',
            ElementType.way: {
                'fence': 'barrier_wall.20.webp',
                'wall': 'barrier_wall.20.webp',
                # TODO: 'hedge': '',
            },
        },
        'building': {
            'bunker': 'military_bunker.webp',
            ElementType.way: {
                None: 'building.webp',
            },
        },
        'crab': {
            'yes': 'crab_yes.webp',  # please don't spoil it :-)
        },
        'diplomatic': {
            'embassy': 'diplomatic_embassy.16.webp',
        },
        'emergency': {
            'assembly_point': 'emergency_assembly_point.webp',
            'defibrillator': 'emergency_defibrillator.webp',
            'fire_extinguisher': 'emergency_fire_extinguisher.webp',
            'fire_hose': 'emergency_fire_hose.webp',
            'fire_hydrant': 'emergency_fire_hydrant.webp',
            'phone': 'emergency_phone.webp',
            'siren': 'emergency_siren.webp',
        },
        'ford': {
            None: 'ford_yes.webp',
        },
        'highway': {
            'bus_stop': 'highway_bus_stop.16.webp',
            'crossing': 'highway_crossing_zebra.webp',
            'elevator': 'passage_elevator.webp',
            'mini_roundabout': 'highway_mini_roundabout.16.webp',
            'passing_place': 'mountain_pass.webp',
            'traffic_signals': 'highway_traffic_signals.16.webp',
            'turning_circle': 'highway_turning_circle.16.webp',
            'turning_loop': 'highway_turning_circle.16.webp',
            # TODO: 'speed_camera': '',
            'street_lamp': 'man_made_lamp.webp',
            ElementType.way: {
                'bridleway': 'highway_bridleway.20.webp',
                'cycleway': 'highway_cycleway.20.webp',
                'footway': 'highway_footway.20.webp',
                'living_street': 'highway_service.20.webp',
                'motorway': 'highway_motorway.20.webp',
                'motorway_link': 'highway_motorway.20.webp',
                'path': 'highway_path.20.webp',
                'pedestrian': 'highway_service.20.webp',
                'primary': 'highway_primary.20.webp',
                'primary_link': 'highway_primary.20.webp',
                'residential': 'highway_unclassified.20.webp',
                'secondary': 'highway_secondary.20.webp',
                'secondary_link': 'highway_secondary.20.webp',
                'service': 'highway_service.20.webp',
                'steps': 'highway_steps.webp',
                'tertiary': 'highway_tertiary.20.webp',
                'track': 'highway_track.20.webp',
                'trunk': 'highway_trunk.20.webp',
                'trunk_link': 'highway_trunk.20.webp',
                'unclassified': 'highway_unclassified.20.webp',
            },
        },
        'historic': {
            'archaeological_site': 'historic_archaeological_site.16.webp',
            'castle': 'historic_castle.webp',
            'memorial': 'historic_memorial.16.webp',
            'mine': 'historic_mine.webp',
            'monument': 'historic_monument.16.webp',
            'ruins': 'tourist_ruins.webp',
            'tomb': 'historic_memorial.16.webp',
            'wayside_cross': 'historic_wayside_cross.webp',
            'wayside_shrine': 'historic_wayside_shrine.webp',
            'wreck': 'historic_wreck.webp',
        },
        'industrial': {
            ElementType.way: {
                'port': 'industrial_port.webp',
            },
        },
        'landuse': {
            ElementType.way: {
                'allotments': 'landuse_allotments.webp',
                'basin': 'water_lake.webp',
                'brownfield': 'landuse_brownfield.webp',
                'cemetery': 'landuse_cemetery.webp',
                'commercial': 'landuse_commercial.webp',
                'farmland': 'landuse_farmland.webp',
                'farmyard': 'landuse_farmyard.webp',
                'forest': 'landuse_forest.webp',
                'grass': 'landuse_grass.10.webp',
                'industrial': 'landuse_industrial.webp',
                'meadow': 'landuse_meadow.webp',
                'military': 'landuse_military.webp',
                # TODO: 'orchard': '',
                'recreational_ground': 'leisure_sports_centre.webp',
                'reservoir': 'water_lake.webp',
                'residential': 'landuse_residential.webp',
                'retail': 'landuse_retail.webp',
                'tourism': 'landuse_tourism.webp',
                'village_green': 'landuse_grass.10.webp',
                # TODO: 'vineyard': '',
                'quarry': 'landuse_quarry.webp',
            },
        },
        'leisure': {
            'marina': 'leisure_marina.webp',
            'slipway': 'leisure_slipway.webp',
            ElementType.way: {
                'garden': 'landuse_grass.10.webp',
                'golf_course': 'leisure_golf_course.webp',
                'nature_reserve': 'leisure_natural_reserve.webp',
                'park': 'leisure_park.webp',
                'pitch': 'leisure_pitch.webp',
                'playground': 'leisure_playground.16.webp',
                'sports_centre': 'leisure_sports_centre.webp',
                'swimming_pool': 'water_lake.webp',
                'water_park': 'leisure_water_park.16.webp',
            },
        },
        'man_made': {
            'crane': 'man_made_crane.webp',
            'lighthouse': 'man_made_lighthouse.16.webp',
            'mast': 'man_made_communications_tower.webp',
            'storage_tank': 'man_made_water_tower.webp',
            'surveillance': 'man_made_surveillance.webp',
            'survey_point': 'man_made_survey_point.webp',
            'tower': 'man_made_lookout_tower.webp',
            'utility_pole': 'power_pole.webp',
            'water_tower': 'man_made_water_tower.16.webp',
            'windmill': 'man_made_windmill.16.webp',
            ElementType.way: {
                'bridge': 'man_made_bridge.20.webp',
                'tunnel': 'man_made_tunnel.20.webp',
            },
        },
        'military': {
            'bunker': 'military_bunker.webp',
        },
        'natural': {
            'cave_entrance': 'natural_cave_entrance.webp',
            'peak': 'natural_peak.webp',
            'tree': 'natural_tree.webp',
            ElementType.way: {
                'grassland': 'natural_grassland.webp',
                'heath': 'natural_heath.webp',
                'scrub': 'natural_scrub.webp',
                'water': 'water_lake.webp',
                'wood': 'natural_wood.webp',
            },
        },
        'place': {
            None: 'place_town.webp',
        },
        'plant:method': {
            'combustion': 'power_plant_coal.webp',
            'photovoltaic': 'power_plant_photovoltaic.webp',
            'run-of-river': 'power_plant_hydro.webp',
            'wind_turbine': 'power_plant_wind.webp',
            'water-pumped-storage': 'power_plant_hydro.webp',
            'water-storage': 'power_plant_hydro.webp',
        },
        'power': {
            'pole': 'power_pole.webp',
            'substation': 'power_substation.webp',
            'tower': 'power_tower.webp',
            'transformer': 'power_transformer.webp',
        },
        'railway': {
            'halt': 'railway_halt.16.webp',
            'level_crossing': 'railway_level_crossing.16.webp',
            'station': 'railway_station.16.webp',
            'subway_entrance': 'railway_subway_entrance.32.webp',
            'tram_level_crossing': 'railway_level_crossing.16.webp',
            'tram_stop': 'railway_subway_entrance.32.webp',
            ElementType.way: {
                'light_rail': 'railway_light_rail.20.webp',
                'rail': 'railway_rail.20.webp',
                'subway': 'railway_subway.20.webp',
                'tram': 'railway_tram.20.webp',
            },
        },
        'shop': {
            None: 'shop_convenience.webp',
            'alcohol': 'shop_alcohol.16.webp',
            'anime': 'shop_anime.webp',
            'bakery': 'shop_bakery.16.webp',
            'beauty': 'shop_beauty.webp',
            'bicycle': 'shop_bicycle.16.webp',
            'books': 'shop_books.16.webp',
            'boutique': 'shop_clothes.16.webp',
            'butcher': 'shop_butcher.webp',
            'camera': 'shop_photo.webp',
            'car': 'shop_car.webp',
            'car_parts': 'shop_car_parts.16.webp',
            'car_repair': 'shop_car_repair.16.webp',
            'chocolate': 'shop_confectionery.webp',
            'clothes': 'shop_clothes.16.webp',
            'computer': 'shop_computer.webp',
            'confectionery': 'shop_confectionery.webp',
            'convenience': 'shop_convenience.webp',
            'copyshop': 'shop_copyshop.webp',
            'department_store': 'shop_department_store.webp',
            'doityourself': 'shop_doityourself.16.webp',
            'e-cigarette': 'shop_tobacco.webp',
            'electronics': 'shop_electronics.16.webp',
            'erotic': 'shop_erotic.webp',
            'estate_agent': 'shop_estate_agent.16.webp',
            'farm': 'shop_greengrocer.webp',
            'fishing': 'shop_fishing.webp',
            'florist': 'shop_florist.16.webp',
            'furniture': 'shop_furniture.16.webp',
            'garden_centre': 'shop_garden_centre.webp',
            'gift': 'shop_gift.16.webp',
            'greengrocer': 'shop_greengrocer.webp',
            'hardware': 'shop_doityourself.16.webp',
            'hairdresser': 'shop_hairdresser.16.webp',
            'hairdresser_supply': 'shop_hairdresser.16.webp',
            'health_food': 'shop_greengrocer.webp',
            'hearing_aids': 'shop_hearing_aids.webp',
            'hifi': 'shop_hifi.webp',
            'interior_decoration': 'shop_furniture.16.webp',
            'jewelry': 'shop_jewelry.16.webp',
            'kiosk': 'shop_kiosk.webp',
            'laundry': 'shop_laundry.webp',
            'mall': 'shop_department_store.webp',
            'mobile_phone': 'shop_mobile_phone.16.webp',
            'motorcycle': 'shop_motorcycle.webp',
            'music': 'shop_music.webp',
            'newsagent': 'shop_newsagent.webp',
            'optician': 'shop_optician.16.webp',
            'pastry': 'shop_confectionery.webp',
            'pet': 'shop_pet.16.webp',
            'photo': 'shop_photo.webp',
            'seafood': 'shop_seafood.webp',
            'shoes': 'shop_shoes.16.webp',
            'supermarket': 'shop_supermarket.16.webp',
            'tobacco': 'shop_tobacco.webp',
            'toys': 'shop_toys.webp',
            'wine': 'shop_alcohol.16.webp',
        },
        'tourism': {
            'alpine_hut': 'tourism_alpine_hut.webp',
            'artwork': 'tourism_artwork.webp',
            'attraction': 'tourism_attraction.webp',
            'camp_site': 'tourism_camp_site.webp',
            'caravan_site': 'tourism_caravan_site.16.webp',
            'chalet': 'tourism_chalet.webp',
            'gallery': 'tourism_gallery.webp',
            'hostel': 'tourism_hostel.16.webp',
            'hotel': 'tourism_hotel.16.webp',
            'information': 'tourism_information.webp',
            'motel': 'tourism_motel.16.webp',
            'museum': 'tourism_museum.16.webp',
            'picnic_site': 'tourism_picnic_site.16.webp',
            'theme_park': 'tourism_theme_park.webp',
            'viewpoint': 'tourism_viewpoint.webp',
            'wilderness_hut': 'tourism_wilderness_hut.16.webp',
            'zoo': 'tourism_zoo.webp',
        },
        'traffic_calming': {
            'bump': 'traffic_calming_bump.webp',
            'cushion': 'traffic_calming_bump.webp',
            'hump': 'traffic_calming_bump.webp',
            'table': 'traffic_calming_bump.webp',
        },
        'water': {
            ElementType.way: {
                None: 'water_lake.webp',
            },
        },
        'waterway': {
            'dam': 'water_dam.webp',
            'weir': 'water_weir.webp',
            ElementType.way: {
                None: 'water_lake.webp',
            },
        },
    }
)

_CONFIG_KEYS_SET = frozenset(_CONFIG)


class ElementIcon:
    @staticmethod
    def get_filename_and_title(element: Element) -> tuple[str, str] | tuple[None, None]:
        """
        Get the filename and title of the icon for an element.

        >>> ElementIcon.get_filename({'aeroway': 'terminal'})
        'aeroway_terminal.webp', 'aeroway=terminal'
        """

        tags = element.tags

        # small optimization, majority of the elements don't have any tags
        if not tags:
            return None, None

        config_keys = _CONFIG_KEYS_SET.intersection(tags)

        for key in config_keys:
            key_value = tags[key]
            key_config = _CONFIG[key]
            key_type_config = key_config.get(element.type)

            # prefer type-specific configuration
            if key_type_config and (icon := key_type_config.get(key_value)):
                return icon, f'{key}={key_value}'
            if icon := key_config.get(key_value):
                return icon, f'{key}={key_value}'

        for key in config_keys:
            key_config = _CONFIG[key]
            key_type_config = key_config.get(element.type)

            # prefer type-specific configuration
            if key_type_config and (icon := key_type_config.get(None)):
                return icon, key
            if icon := key_config.get(None):
                return icon, key

        return None, None

    # TODO: deleted objects use previous tagging
    # TODO: test
    @staticmethod
    def raise_if_file_missing() -> None:
        """
        Raise an exception if any of the icon files are missing.
        """

        for key_config in _CONFIG.values():
            for icon_or_type_config in key_config.values():
                if isinstance(icon_or_type_config, str):
                    icon = icon_or_type_config
                    icons = (icon,)
                else:
                    key_type_config = icon_or_type_config
                    icons = key_type_config.values()

                for icon in icons:
                    path = pathlib.Path('static/img/element/' + icon)
                    if not path.is_file():
                        raise FileNotFoundError(path)
