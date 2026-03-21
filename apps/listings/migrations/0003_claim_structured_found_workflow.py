from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0002_rename_listings_it_item_ty_f14ec5_idx_listings_it_item_ty_337ff3_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="claim",
            name="full_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="claim",
            name="lost_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="claim",
            name="lost_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="claims_lost_here",
                to="listings.campuslocation",
            ),
        ),
        migrations.AddField(
            model_name="claim",
            name="lost_location_details",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="claim",
            name="relationship_to_item",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="claim",
            name="student_card_image",
            field=models.ImageField(blank=True, upload_to="claims/student_cards/%Y/%m/%d"),
        ),
        migrations.AddField(
            model_name="claim",
            name="student_id",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
