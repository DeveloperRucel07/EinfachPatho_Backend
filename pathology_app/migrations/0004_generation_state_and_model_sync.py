# Generated manually to sync the existing database schema with the current models.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pathology_app', '0003_alter_disease_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DiseaseGenerationState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('normalized_name', models.CharField(db_index=True, max_length=255, unique=True)),
                ('original_name', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('GENERATING', 'Generating'), ('READY', 'Ready'), ('FAILED', 'Failed')], db_index=True, default='PENDING', max_length=20)),
                ('generated_at', models.DateTimeField(blank=True, null=True)),
                ('ai_model', models.CharField(blank=True, default='', max_length=100)),
                ('generation_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('disease', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generation_state', to='pathology_app.disease')),
            ],
            options={
                'ordering': ['normalized_name'],
            },
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('score', models.PositiveIntegerField(default=0)),
                ('total', models.PositiveIntegerField(default=0)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='pathology_app.quiz')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quiz_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='QuestionAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selected_index', models.IntegerField()),
                ('is_correct', models.BooleanField()),
                ('answered_at', models.DateTimeField(auto_now_add=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='pathology_app.quizattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pathology_app.question')),
            ],
            options={
                'ordering': ['question_id'],
            },
        ),
        migrations.RenameField(
            model_name='durstdata',
            old_name='ursachen_text',
            new_name='ursachen',
        ),
        migrations.RenameField(
            model_name='question',
            old_name='question_title',
            new_name='question',
        ),
        migrations.RenameField(
            model_name='question',
            old_name='question_options',
            new_name='options',
        ),
        migrations.AlterModelOptions(
            name='disease',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='durstdata',
            options={'ordering': ['disease'], 'verbose_name': 'Durst Data', 'verbose_name_plural': 'Durst Data'},
        ),
        migrations.AlterModelOptions(
            name='immediateaction',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='question',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='quiz',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='riskfactor',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='source',
            options={'ordering': ['source_name']},
        ),
        migrations.AlterModelOptions(
            name='symptom',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='ursachekeyword',
            options={'ordering': ['keyword']},
        ),
        migrations.AlterField(
            model_name='disease',
            name='disease_id',
            field=models.CharField(db_index=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='disease',
            name='name',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='disease',
            name='category',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='durstdata',
            name='diagnostic_gold_standard',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='durstdata',
            name='guideline_link',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='durstdata',
            name='red_flags',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='explanation',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='quiz',
            name='title',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='source',
            name='source_name',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='ursachekeyword',
            name='keyword',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='disease',
            unique_together={('owner', 'disease_id')},
        ),
        migrations.AlterUniqueTogether(
            name='source',
            unique_together={('disease', 'link')},
        ),
        migrations.AlterUniqueTogether(
            name='ursachekeyword',
            unique_together={('durst_data', 'keyword')},
        ),
        migrations.AlterUniqueTogether(
            name='questionanswer',
            unique_together={('attempt', 'question')},
        ),
    ]