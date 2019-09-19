import pytest
from django.test import TestCase

from environments.models import Environment, Identity, Trait
from features.models import Feature, FeatureState
from organisations.models import Organisation
from projects.models import Project
from util.tests import Helper


@pytest.mark.django_db
class EnvironmentSaveTestCase(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Test Org")
        self.project = Project.objects.create(name="Test Project", organisation=self.organisation)
        self.feature = Feature.objects.create(name="Test Feature", project=self.project)
        # The environment is initialised in a non-saved state as we want to test the save
        # functionality.
        self.environment = Environment(name="Test Environment", project=self.project)

    def test_environment_should_be_created_with_feature_states(self):
        # Given - set up data

        # When
        self.environment.save()

        # Then
        feature_states = FeatureState.objects.filter(environment=self.environment)
        assert hasattr(self.environment, 'api_key')
        assert feature_states.count() == 1

    def test_environment_can_be_created_with_webhooks_enabled(self):
        environment_with_webhook = Environment.objects.create(name="Env with Webhooks",
                                                              project=self.project,
                                                              webhooks_enabled=True,
                                                              webhook_url="https://sometesturl.org")

        self.assertTrue(environment_with_webhook.name)

    def test_on_creation_save_feature_states_get_created(self):
        # These should be no feature states before saving
        self.assertEqual(FeatureState.objects.count(), 0)

        self.environment.save()

        # On the first save a new feature state should be created
        self.assertEqual(FeatureState.objects.count(), 1)

    def test_on_update_save_feature_states_get_updated_not_created(self):
        self.environment.save()

        self.feature.default_enabled = True
        self.feature.save()
        self.environment.save()

        self.assertEqual(FeatureState.objects.count(), 1)

    def test_on_creation_save_feature_is_created_with_the_correct_default(self):
        self.environment.save()
        self.assertFalse(FeatureState.objects.get().enabled)

    def test_on_update_save_feature_gets_updated_with_the_correct_default(self):
        self.environment.save()
        self.assertFalse(FeatureState.objects.get().enabled)

        self.feature.default_enabled = True
        self.feature.save()

        self.environment.save()
        self.assertTrue(FeatureState.objects.get().enabled)

    def test_on_update_save_feature_states_dont_get_updated_if_identity_present(self):
        self.environment.save()
        identity = Identity.objects.create(identifier="test-identity", environment=self.environment)

        fs = FeatureState.objects.get()
        fs.id = None
        fs.identity = identity
        fs.save()
        self.assertEqual(FeatureState.objects.count(), 2)

        self.feature.default_enabled = True
        self.feature.save()
        self.environment.save()
        fs.refresh_from_db()

        self.assertNotEqual(fs.enabled, FeatureState.objects.exclude(id=fs.id).get().enabled)


class IdentityTestCase(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Test Org")
        self.project = Project.objects.create(name="Test Project", organisation=self.organisation)
        self.environment = Environment.objects.create(name="Test Environment", project=self.project)

    def tearDown(self) -> None:
        Helper.clean_up()

    def test_create_identity_should_assign_relevant_attributes(self):
        identity = Identity.objects.create(identifier="test-identity", environment=self.environment)

        assert isinstance(identity.environment, Environment)
        assert hasattr(identity, 'created_date')

    def test_get_all_feature_states(self):
        feature = Feature.objects.create(name="Test Feature", project=self.project)
        feature_2 = Feature.objects.create(name="Test Feature 2", project=self.project)
        environment_2 = Environment.objects.create(name="Test Environment 2", project=self.project)

        identity_1 = Identity.objects.create(
            identifier="test-identity-1",
            environment=self.environment,
        )
        identity_2 = Identity.objects.create(
            identifier="test-identity-2",
            environment=self.environment,
        )
        identity_3 = Identity.objects.create(
            identifier="test-identity-3",
            environment=environment_2,
        )

        # User unassigned - automatically should be created via `Feature` save method.
        fs_environment_anticipated = FeatureState.objects.get(
            feature=feature_2,
            environment=self.environment,
        )

        # User assigned
        fs_identity_anticipated = FeatureState.objects.create(
            feature=feature,
            environment=self.environment,
            identity=identity_1,
        )
        FeatureState.objects.create(
            feature=feature,
            environment=self.environment,
            identity=identity_2,
        )
        FeatureState.objects.create(
            feature=feature,
            environment=environment_2,
            identity=identity_3,
        )

        # For identity_1 all items in a different environment should not appear. Identity
        # specific flags should be returned as well as non-identity specific ones that have not
        # already been returned via the identity specific result.
        flags = identity_1.get_all_feature_states()
        self.assertEqual(len(flags), 2)
        self.assertIn(fs_environment_anticipated, flags)
        self.assertIn(fs_identity_anticipated, flags)

    def test_create_trait_should_assign_relevant_attributes(self):
        identity = Identity.objects.create(identifier='test-identity', environment=self.environment)
        trait = Trait.objects.create(trait_key="test-key", string_value="testing trait", identity=identity)

        self.assertIsInstance(trait.identity, Identity)
        self.assertTrue(hasattr(trait, 'trait_key'))
        self.assertTrue(hasattr(trait, 'value_type'))
        self.assertTrue(hasattr(trait, 'created_date'))

    def test_on_update_trait_should_update_relevant_attributes(self):
        identity = Identity.objects.create(identifier='test-identifier', environment=self.environment)
        trait = Trait.objects.create(trait_key="test-key", string_value="testing trait", identity=identity)

        # TODO: need tests for updates

    def test_get_all_traits_for_identity(self):
        identity = Identity.objects.create(identifier='test-identifier', environment=self.environment)
        identity2 = Identity.objects.create(identifier="test-identity_two", environment=self.environment)

        Trait.objects.create(trait_key="test-key-one", string_value="testing trait", identity=identity)
        Trait.objects.create(trait_key="test-key-two", string_value="testing trait", identity=identity)
        Trait.objects.create(trait_key="test-key-three", string_value="testing trait", identity=identity)
        Trait.objects.create(trait_key="test-key-three", string_value="testing trait", identity=identity2)

        # Identity one should have 3
        traits_identity_one = identity.get_all_user_traits()
        self.assertEqual(len(traits_identity_one), 3)

        traits_identity_two = identity2.get_all_user_traits()
        self.assertEqual(len(traits_identity_two), 1)
