from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, CitizenProfile, StaffProfile, AdminProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.user_type == 'Citizen':
            CitizenProfile.objects.create(user=instance)
        elif instance.user_type == 'Council Staff':
            StaffProfile.objects.create(user=instance)
        elif instance.user_type == 'Admin':
            AdminProfile.objects.create(user=instance)


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if instance.user_type == 'Citizen':
        try:
            instance.citizenprofile.save()
        except CitizenProfile.DoesNotExist:
            # CreatorProfile doesn't exist, create it or just pass
            CitizenProfile.objects.create(user=instance)
    elif instance.user_type == 'Council Staff':
        try:
            instance.staffprofile.save()
        except StaffProfile.DoesNotExist:
            StaffProfile.objects.create(user=instance)
    elif instance.user_type == 'Admin':
        try:
            instance.adminprofile.save()
        except AdminProfile.DoesNotExist:
            AdminProfile.objects.create(user=instance)





