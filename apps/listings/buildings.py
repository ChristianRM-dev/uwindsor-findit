from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from apps.listings.models import CampusLocation, Claim, Item


BUILDING_EMPTY_LABEL = "Select building"


@dataclass(frozen=True)
class CampusBuildingDefinition:
    name: str
    code: str
    legacy_names: tuple[str, ...] = ()


OFFICIAL_CAMPUS_BUILDINGS = (
    CampusBuildingDefinition(name="300 Ouellette", code="300-ouellette"),
    CampusBuildingDefinition(
        name="Assumption Chapel",
        code="assumption-hall",
        legacy_names=("Assumption Hall",),
    ),
    CampusBuildingDefinition(
        name="Centre for Automotive Research",
        code="centre-for-automotive-research",
    ),
    CampusBuildingDefinition(name="Biology Building", code="biology-building"),
    CampusBuildingDefinition(name="Canterbury College", code="canterbury-college"),
    CampusBuildingDefinition(
        name="Centre For Engineering Innovation",
        code="engineering-building",
        legacy_names=("Engineering Building",),
    ),
    CampusBuildingDefinition(name="Chrysler Hall North", code="chrysler-hall-north"),
    CampusBuildingDefinition(name="Chrysler Hall South", code="chrysler-hall-south"),
    CampusBuildingDefinition(name="167 Ferry (Downtown)", code="167-ferry-downtown"),
    CampusBuildingDefinition(name="Drama Building", code="drama-building"),
    CampusBuildingDefinition(name="Dillon Hall", code="dillon-hall"),
    CampusBuildingDefinition(name="Neal Education Building", code="neal-education-building"),
    CampusBuildingDefinition(name="Essex Hall", code="essex-hall"),
    CampusBuildingDefinition(name="Erie Hall", code="erie-hall"),
    CampusBuildingDefinition(
        name="HK Building",
        code="human-kinetics",
        legacy_names=("Human Kinetics Building",),
    ),
    CampusBuildingDefinition(
        name="Jackman Dramatic Art Centre",
        code="jackman-dramatic-art-centre",
    ),
    CampusBuildingDefinition(name="Ianni Law Building", code="ianni-law-building"),
    CampusBuildingDefinition(name="LeBel Building", code="lebel-building"),
    CampusBuildingDefinition(name="Leddy Library", code="leddy-library"),
    CampusBuildingDefinition(name="Lambton Tower", code="lambton-tower"),
    CampusBuildingDefinition(
        name="O'Neil Medical Education Centre",
        code="oneil-medical-education-centre",
    ),
    CampusBuildingDefinition(name="Memorial Hall", code="memorial-hall"),
    CampusBuildingDefinition(name="Music Building", code="music-building"),
    CampusBuildingDefinition(name="Odette Building", code="odette-building"),
    CampusBuildingDefinition(name="St. Denis Center", code="st-denis-center"),
    CampusBuildingDefinition(name="St. Francis School", code="st-francis-school"),
    CampusBuildingDefinition(
        name="Toldo Health Education Centre",
        code="toldo-health-centre",
    ),
    CampusBuildingDefinition(
        name="C.A.W. Student Centre",
        code="caw-student-centre",
        legacy_names=("CAW Student Centre",),
    ),
    CampusBuildingDefinition(name="West Library", code="west-library"),
)

OFFICIAL_CAMPUS_BUILDING_CODES = tuple(building.code for building in OFFICIAL_CAMPUS_BUILDINGS)


def order_campus_location_queryset(queryset: QuerySet[CampusLocation]) -> QuerySet[CampusLocation]:
    order_by_official_catalog = Case(
        *[
            When(code=building.code, then=Value(index))
            for index, building in enumerate(OFFICIAL_CAMPUS_BUILDINGS)
        ],
        default=Value(len(OFFICIAL_CAMPUS_BUILDINGS)),
        output_field=IntegerField(),
    )
    return queryset.order_by(order_by_official_catalog, "name")


def get_active_campus_location_queryset() -> QuerySet[CampusLocation]:
    return order_campus_location_queryset(CampusLocation.objects.filter(is_active=True))


def sync_official_campus_locations(
    *,
    CampusLocationModel=CampusLocation,
    ItemModel=Item,
    ClaimModel=Claim,
) -> dict[str, int]:
    stats = {
        "created": 0,
        "renamed": 0,
        "reactivated": 0,
        "merged_duplicates": 0,
    }

    for building in OFFICIAL_CAMPUS_BUILDINGS:
        matching_locations = list(
            CampusLocationModel.objects.filter(
                Q(code=building.code)
                | Q(name=building.name)
                | Q(name__in=building.legacy_names)
            )
        )
        matching_locations.sort(
            key=lambda location: (
                0 if location.code == building.code else 1,
                0 if location.name == building.name else 1,
                0 if location.name in building.legacy_names else 1,
                location.pk,
            )
        )

        primary_location = matching_locations[0] if matching_locations else None
        duplicate_locations = matching_locations[1:]

        if primary_location is None:
            CampusLocationModel.objects.create(
                name=building.name,
                code=building.code,
                is_active=True,
            )
            stats["created"] += 1
            continue

        for duplicate_location in duplicate_locations:
            ItemModel.objects.filter(location_id=duplicate_location.pk).update(location_id=primary_location.pk)
            ClaimModel.objects.filter(lost_location_id=duplicate_location.pk).update(lost_location_id=primary_location.pk)
            duplicate_location.delete()
            stats["merged_duplicates"] += 1

        fields_to_update: list[str] = []
        if primary_location.name != building.name:
            primary_location.name = building.name
            stats["renamed"] += 1
            fields_to_update.append("name")
        if primary_location.code != building.code:
            primary_location.code = building.code
            fields_to_update.append("code")
        if not primary_location.is_active:
            primary_location.is_active = True
            stats["reactivated"] += 1
            fields_to_update.append("is_active")

        if fields_to_update:
            primary_location.save(update_fields=[*fields_to_update, "updated_at"])

    return stats
