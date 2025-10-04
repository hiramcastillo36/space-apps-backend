"""
Tests for models.
"""
from django.forms import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import (
    Area, AreaHierarchy, Objective,
    KeyResult, OrganizationArea, UserObjective, AreaObjective,
    Organization, Worker, AreaWorker, WorkerAssignation,
    AreaKeyResult,
)
from django.db.utils import IntegrityError
from django.db import transaction


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_successful(self):
        """Test creating a new user with an email is successful."""
        email = 'test@example-com'
        password = 'TestPass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test the email for a new user is normalized."""
        sample_emails = [
            ['test1@EXAMPLE.com', 'test1@example.com'],
            ['Test2@Example.com', 'Test2@example.com'],
            ['TEST3@EXAMPLE.com', 'TEST3@example.com'],
            ['test4@example.COM', 'test4@example.com'],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, 'sample123')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        """Test creating user without email raises error."""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'sample123')

    def test_create_superuser(self):
        """Test creating a new superuser."""
        user = get_user_model().objects.create_superuser(
            'superuser@example.com',
            'superuser123'
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_area_str(self):
        """Test the area string representation."""
        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        self.assertEqual(str(area), area.name)
        self.assertEqual(area.description, "Engineering department")
        self.assertEqual(area.slug, "engineering")

    def test_area_slug_creation(self):
        """Test that slugs are automatically created from the name."""
        area = Area.objects.create(
            name='Software Engineering',
            description='Software Engineering department'
        )
        self.assertEqual(area.slug, "software-engineering")

    def test_area_unique_slug(self):
        """Test that slugs must be unique."""

        area1 = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        with transaction.atomic():
            area2 = Area.objects.create(
                name='Engineering',
                description='Another Engineering department'
            )

            self.assertNotEqual(area1.slug, area2.slug)
            self.assertTrue(area2.slug.startswith("engineering-"))

    def test_slug_duplicate_prevention(self):
        """Test that explicitly trying to create a duplicate slug raises an error."""  # noqa
        Area.objects.create(
            name='Engineering',
            description='Engineering department',
            slug='engineering-dept'
        )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Area.objects.create(
                    name='Different Engineering',
                    description='Different department',
                    slug='engineering-dept'
                )

    def test_area_only_required_fields(self):
        """Test the area string representation."""
        area = Area.objects.create(
            name='Engineering',
        )

        self.assertEqual(str(area), area.name)

    def test_area_hierarchy_str(self):
        """Test the area hierarchy string representation."""
        parent_area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        child_area = Area.objects.create(
            name='Software',
            description='Software department'
        )
        hierarchy = AreaHierarchy.objects.create(
            ancestor=parent_area,
            descendant=child_area,
            depth=1
        )

        self.assertEqual(str(hierarchy), f'{parent_area} -> {child_area}')

    def test_area_hierarchy(self):
        """Test area hierarchy."""
        parent_area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        child_area = Area.objects.create(
            name='Software',
            description='Software department'
        )
        hierarchy = AreaHierarchy.objects.create(
            ancestor=parent_area,
            descendant=child_area,
            depth=1
        )

        self.assertEqual(parent_area.descendants.first().descendant,
                         child_area)
        self.assertEqual(child_area.ancestors.first().ancestor, parent_area)
        self.assertEqual(hierarchy.depth, 1)

    def test_area_hierarchy_depth(self):
        """Test area hierarchy depth."""
        parent_area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        child_area = Area.objects.create(
            name='Software',
            description='Software department'
        )
        AreaHierarchy.objects.create(
            ancestor=parent_area,
            descendant=child_area,
            depth=1
        )

        self.assertEqual(parent_area.descendants.first().depth, 1)
        self.assertEqual(child_area.ancestors.first().depth, 1)

    def test_area_hierarchy_unique_together(self):
        """Test area hierarchy unique together."""
        parent_area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        child_area = Area.objects.create(
            name='Software',
            description='Software department'
        )
        AreaHierarchy.objects.create(
            ancestor=parent_area,
            descendant=child_area,
            depth=1
        )

        with self.assertRaises(IntegrityError):
            AreaHierarchy.objects.create(
                ancestor=parent_area,
                descendant=child_area,
                depth=1
            )

    def test_area_hierarchy_indexes(self):
        """Test area hierarchy indexes."""
        parent_area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        child_area = Area.objects.create(
            name='Software',
            description='Software department'
        )
        AreaHierarchy.objects.create(
            ancestor=parent_area,
            descendant=child_area,
            depth=1
        )

        self.assertTrue('ancestor' in AreaHierarchy._meta.indexes[0].fields)
        self.assertTrue('descendant' in AreaHierarchy._meta.indexes[1].fields)

    def test_objective_str(self):
        """Test the objective string representation."""
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )

        self.assertEqual(str(objective), objective.name)

    def test_key_result_str(self):
        """Test the key result string representation."""

        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )

        parent_key_result = KeyResult.objects.create(
            name='Parent Key Result',
            description='Parent Key Result description',
            status=False,
            is_root=True,
            is_worker_assignation=False,
            objective=objective
        )

        key_result = KeyResult.objects.create(
            name='Key Result 1',
            description='Key Result 1 description',
            status=False,
            is_root=False,
            is_worker_assignation=False,
            key_result=parent_key_result,
        )

        self.assertEqual(str(key_result), key_result.name)

    def test_key_result_with_field_null(self):
        """Test the key result with key_result null"""
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )
        key_result = KeyResult.objects.create(
            name='Key Result 1',
            description='Key Result 1 description',
            status=False,
            is_root=False,
            is_worker_assignation=False,
            key_result=None,
            objective=objective,
        )

        self.assertEqual(str(key_result), key_result.name)

    def test_key_result_status(self):
        """Test the key result status."""
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )
        key_result = KeyResult.objects.create(
            name='Key Result 1',
            description='Key Result 1 description',
            status=False,
            is_root=False,
            is_worker_assignation=False,
            objective=objective,
        )

        self.assertFalse(key_result.status)

    def test_area_key_result(self):
        """Test area key_result"""
        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )
        key_result = KeyResult.objects.create(
            name='Key Result 1',
            description='Key Result 1 description',
            status=False,
            is_root=False,
            is_worker_assignation=False,
            key_result=None,
            objective=objective,
        )

        area_key_result = AreaKeyResult.objects.create(
            area=area,
            key_result=key_result,
        )

        self.assertEqual(str(area_key_result), f'{area} -> {key_result}')

    def test_user_objective(self):
        """Test user objective."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False,
        )

        user_objective = UserObjective.objects.create(
            user=user,
            objective=objective
        )

        self.assertEqual(user_objective.user, user)
        self.assertEqual(user_objective.objective, objective)

    def test_user_objective_str(self):
        """Test user objective string representation."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False,
        )

        user_objective = UserObjective.objects.create(
            user=user,
            objective=objective
        )

        self.assertEqual(str(user_objective), f'{user} -> {objective}')

    def test_area_objective(self):
        """Test area objective."""
        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False,
        )

        area_objective = AreaObjective.objects.create(
            area=area,
            objective=objective
        )

        self.assertEqual(area_objective.area, area)
        self.assertEqual(area_objective.objective, objective)

    def test_area_objective_str(self):
        """Test area objective string representation."""
        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )
        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False,
        )

        area_objective = AreaObjective.objects.create(
            area=area,
            objective=objective
        )

        self.assertEqual(str(area_objective), f'{area} -> {objective}')

    def test_create_organization(self):
        """Test organization."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        self.assertEqual(organization.user, user)
        self.assertEqual(organization.name, 'Organization 1')
        self.assertEqual(organization.slug, 'organization-1')

    def test_organization_unique_slug(self):
        """Test unique organization slug."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        with transaction.atomic():
            organization = Organization.objects.create(
                name='Organization 1',
                code='ORG2',
                user=user
            )

            self.assertNotEqual(organization.slug, 'organization-1')
            self.assertTrue(organization.slug.startswith("organization-1-"))

    def test_unique_organization_code(self):
        """Test unique organization code."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        with self.assertRaises(IntegrityError):
            Organization.objects.create(
                name='Organization 2',
                code='ORG1',
                user=user
            )

    def test_create_organization_area(self):
        """Test organization area."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        organization_area = OrganizationArea.objects.create(
            organization=organization,
            area=area,
            is_root=True
        )

        self.assertEqual(organization_area.organization, organization)
        self.assertEqual(organization_area.area, area)
        self.assertTrue(organization_area.is_root)

    def test_create_organization_area_without_root(self):
        """Test organization area without root."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        OrganizationArea.objects.create(
            organization=organization,
            area=area,
            is_root=True
        )

        organization_area = OrganizationArea.objects.create(
            organization=organization,
            area=area,
            is_root=False
        )

        self.assertEqual(organization_area.organization, organization)
        self.assertEqual(organization_area.area, area)
        self.assertFalse(organization_area.is_root)

    def test_unique_organization_area(self):
        """Test unique organization area."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")
        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        OrganizationArea.objects.create(
            organization=organization,
            area=area,
            is_root=True
        )

        with self.assertRaises(ValidationError):
            OrganizationArea.objects.create(
                organization=organization,
                area=area,
                is_root=True
            )

    def test_organization_area_str(self):
        """Test organization area string representation."""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")

        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        organization_area = OrganizationArea.objects.create(
            organization=organization,
            area=area,
            is_root=True
        )

        self.assertEqual(str(organization_area), f'{organization} -> {area}')

    def test_worker(self):
        """Test worker"""
        user = get_user_model().objects.create_user("test@email.com",
                                                    "password")

        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        full_name = 'John Doe'
        position = 'Software Engineer'
        is_leader = False
        worker = Worker.objects.create(
            full_name=full_name,
            position=position,
            is_leader=is_leader,
            organization=organization
        )
        self.assertEqual(worker.full_name, full_name)

    def test_worker_creation_with_null_fields(self):
        """Test creating a worker with nullable fields"""
        user = get_user_model().objects.create_user(
            email="test@email.com",
            password="password"
        )

        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        full_name = 'John Doe'
        position = None
        is_leader = False

        worker = Worker.objects.create(
            full_name=full_name,
            position=position,
            is_leader=is_leader,
            organization=organization
        )

        self.assertEqual(worker.full_name, full_name)

    def test_area_worker(self):
        """Test area worker"""
        user = get_user_model().objects.create_user(
            email="test@email.com",
            password="password"
        )

        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        area = Area.objects.create(
            name='Engineering',
            description='Engineering department'
        )

        worker = Worker.objects.create(
            full_name='John Doe',
            position='Software Engineer',
            is_leader=False,
            organization=organization
        )

        area_worker = AreaWorker.objects.create(
            area=area,
            worker=worker,
        )

        self.assertEqual(str(area_worker), f'{area} -> {worker}')

    def test_create_worker_assignation(self):
        """Test worker assignation."""
        user = get_user_model().objects.create_user(
            email="test@email.com",
            password="password"
        )

        organization = Organization.objects.create(
            name='Organization 1',
            code='ORG1',
            user=user
        )

        worker = Worker.objects.create(
            full_name='John Doe',
            position='Software Engineer',
            is_leader=False,
            organization=organization
        )

        objective = Objective.objects.create(
            name='Objective 1',
            description='Objective 1 description',
            status=False
        )

        key_result = KeyResult.objects.create(
            name='Key Result 1',
            description='Key Result 1 description',
            status=False,
            objective=objective
        )

        worker_assignation = WorkerAssignation.objects.create(
            worker=worker,
            key_result=key_result
        )

        self.assertEqual(str(worker_assignation), f'{worker} -> {key_result}')
        self.assertEqual(worker_assignation.worker, worker)
