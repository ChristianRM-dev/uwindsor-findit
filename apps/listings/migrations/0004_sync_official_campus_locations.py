from django.db import migrations
from django.db.models import Q


OFFICIAL_CAMPUS_BUILDINGS = (
    {"name": "300 Ouellette", "code": "300-ouellette", "legacy_names": ()},
    {
        "name": "Assumption Chapel",
        "code": "assumption-hall",
        "legacy_names": ("Assumption Hall",),
    },
    {
        "name": "Centre for Automotive Research",
        "code": "centre-for-automotive-research",
        "legacy_names": (),
    },
    {"name": "Biology Building", "code": "biology-building", "legacy_names": ()},
    {"name": "Canterbury College", "code": "canterbury-college", "legacy_names": ()},
    {
        "name": "Centre For Engineering Innovation",
        "code": "engineering-building",
        "legacy_names": ("Engineering Building",),
    },
    {"name": "Chrysler Hall North", "code": "chrysler-hall-north", "legacy_names": ()},
    {"name": "Chrysler Hall South", "code": "chrysler-hall-south", "legacy_names": ()},
    {"name": "167 Ferry (Downtown)", "code": "167-ferry-downtown", "legacy_names": ()},
    {"name": "Drama Building", "code": "drama-building", "legacy_names": ()},
    {"name": "Dillon Hall", "code": "dillon-hall", "legacy_names": ()},
    {
        "name": "Neal Education Building",
        "code": "neal-education-building",
        "legacy_names": (),
    },
    {"name": "Essex Hall", "code": "essex-hall", "legacy_names": ()},
    {"name": "Erie Hall", "code": "erie-hall", "legacy_names": ()},
    {
        "name": "HK Building",
        "code": "human-kinetics",
        "legacy_names": ("Human Kinetics Building",),
    },
    {
        "name": "Jackman Dramatic Art Centre",
        "code": "jackman-dramatic-art-centre",
        "legacy_names": (),
    },
    {"name": "Ianni Law Building", "code": "ianni-law-building", "legacy_names": ()},
    {"name": "LeBel Building", "code": "lebel-building", "legacy_names": ()},
    {"name": "Leddy Library", "code": "leddy-library", "legacy_names": ()},
    {"name": "Lambton Tower", "code": "lambton-tower", "legacy_names": ()},
    {
        "name": "O'Neil Medical Education Centre",
        "code": "oneil-medical-education-centre",
        "legacy_names": (),
    },
    {"name": "Memorial Hall", "code": "memorial-hall", "legacy_names": ()},
    {"name": "Music Building", "code": "music-building", "legacy_names": ()},
    {"name": "Odette Building", "code": "odette-building", "legacy_names": ()},
    {"name": "St. Denis Center", "code": "st-denis-center", "legacy_names": ()},
    {"name": "St. Francis School", "code": "st-francis-school", "legacy_names": ()},
    {
        "name": "Toldo Health Education Centre",
        "code": "toldo-health-centre",
        "legacy_names": (),
    },
    {
        "name": "C.A.W. Student Centre",
        "code": "caw-student-centre",
        "legacy_names": ("CAW Student Centre",),
    },
    {"name": "West Library", "code": "west-library", "legacy_names": ()},
)


def sync_official_campus_locations(apps, schema_editor):
    CampusLocation = apps.get_model("listings", "CampusLocation")
    Item = apps.get_model("listings", "Item")
    Claim = apps.get_model("listings", "Claim")

    for building in OFFICIAL_CAMPUS_BUILDINGS:
        matching_locations = list(
            CampusLocation.objects.filter(
                Q(code=building["code"])
                | Q(name=building["name"])
                | Q(name__in=building["legacy_names"])
            )
        )
        matching_locations.sort(
            key=lambda location: (
                0 if location.code == building["code"] else 1,
                0 if location.name == building["name"] else 1,
                0 if location.name in building["legacy_names"] else 1,
                location.pk,
            )
        )

        primary_location = matching_locations[0] if matching_locations else None
        duplicate_locations = matching_locations[1:]

        if primary_location is None:
            CampusLocation.objects.create(
                name=building["name"],
                code=building["code"],
                is_active=True,
            )
            continue

        for duplicate_location in duplicate_locations:
            Item.objects.filter(location_id=duplicate_location.pk).update(location_id=primary_location.pk)
            Claim.objects.filter(lost_location_id=duplicate_location.pk).update(lost_location_id=primary_location.pk)
            duplicate_location.delete()

        fields_to_update = []
        if primary_location.name != building["name"]:
            primary_location.name = building["name"]
            fields_to_update.append("name")
        if primary_location.code != building["code"]:
            primary_location.code = building["code"]
            fields_to_update.append("code")
        if not primary_location.is_active:
            primary_location.is_active = True
            fields_to_update.append("is_active")

        if fields_to_update:
            fields_to_update.append("updated_at")
            primary_location.save(update_fields=fields_to_update)


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0003_claim_structured_found_workflow"),
    ]

    operations = [
        migrations.RunPython(sync_official_campus_locations, migrations.RunPython.noop),
    ]
