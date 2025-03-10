# Generated by Django 5.1.6 on 2025-03-10 18:48

import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Категория',
                'verbose_name_plural': 'Категории',
            },
        ),
        migrations.CreateModel(
            name='Parameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Параметр',
                'verbose_name_plural': 'Параметры',
            },
        ),
        migrations.CreateModel(
            name='Shop',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Название')),
                ('created_at', models.DateField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Магазин',
                'verbose_name_plural': 'Магазины',
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Электронная почта')),
                ('username', models.CharField(blank=True, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, null=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('phone', models.CharField(blank=True, max_length=50, null=True, verbose_name='Номер телефона')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.CharField(max_length=50, verbose_name='Город')),
                ('street', models.CharField(max_length=50, verbose_name='Улица')),
                ('house', models.CharField(max_length=50, verbose_name='Дом')),
                ('apartment', models.CharField(blank=True, max_length=50, null=True, verbose_name='Квартира')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contacts', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Контакты пользователя',
                'verbose_name_plural': 'Контакты пользователей',
            },
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(unique=True, verbose_name='Токен сброса пароля')),
                ('exp_time', models.DateTimeField(verbose_name='Действителен до')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reset_token', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Токен сброса пароля',
                'verbose_name_plural': 'Токены сброса пароля',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=50, verbose_name='Модель')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Название')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='autopurchases.category', verbose_name='Категория')),
            ],
            options={
                'verbose_name': 'Товар',
                'verbose_name_plural': 'Товары',
            },
        ),
        migrations.CreateModel(
            name='ProductsParameters',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=50, verbose_name='Значение')),
                ('parameter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products_values', to='autopurchases.parameter', verbose_name='Параметр')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parameters_values', to='autopurchases.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Параметр',
                'verbose_name_plural': 'Параметры',
            },
        ),
        migrations.AddField(
            model_name='product',
            name='parameters',
            field=models.ManyToManyField(related_name='products', through='autopurchases.ProductsParameters', to='autopurchases.parameter', verbose_name='Параметры'),
        ),
        migrations.CreateModel(
            name='ShopsManagers',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_owner', models.BooleanField(default=False, verbose_name='Собственник')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Управляющие')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='autopurchases.shop', verbose_name='Магазины')),
            ],
        ),
        migrations.AddField(
            model_name='shop',
            name='managers',
            field=models.ManyToManyField(related_name='shops', through='autopurchases.ShopsManagers', to=settings.AUTH_USER_MODEL, verbose_name='Управляющие'),
        ),
        migrations.CreateModel(
            name='Stock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='Количество')),
                ('price', models.PositiveBigIntegerField(verbose_name='Цена')),
                ('can_buy', models.BooleanField(default=True, verbose_name='Доступен для заказа')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='autopurchases.product', verbose_name='Товар')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='autopurchases.shop', verbose_name='Магазин')),
            ],
            options={
                'verbose_name_plural': 'Каталог товаров',
            },
        ),
        migrations.AddField(
            model_name='product',
            name='shops',
            field=models.ManyToManyField(related_name='products', through='autopurchases.Stock', to='autopurchases.shop', verbose_name='Магазины'),
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='Количество')),
                ('total_price', models.PositiveBigIntegerField(verbose_name='Итоговая стоимость')),
                ('status', models.CharField(choices=[('in_cart', 'В корзине'), ('created', 'Создан'), ('confirmed', 'Подтвержден'), ('assembled', 'Собран'), ('sent', 'Отправлен'), ('delivered', 'Доставлен'), ('cancelled', 'Отменен')], default='in_cart', max_length=50, verbose_name='Статус заказа')),
                ('created_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Заказчик')),
                ('delivery_address', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='autopurchases.contact', verbose_name='Адрес доставки')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='autopurchases.stock', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Заказ',
                'verbose_name_plural': 'Заказы',
            },
        ),
        migrations.AddConstraint(
            model_name='productsparameters',
            constraint=models.UniqueConstraint(fields=('product', 'parameter', 'value'), name='unique-product-parameter'),
        ),
        migrations.AddConstraint(
            model_name='stock',
            constraint=models.UniqueConstraint(fields=('shop', 'product'), name='unique-shop-product'),
        ),
    ]
