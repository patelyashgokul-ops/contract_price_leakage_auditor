from decimal import Decimal

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'


def _dec(value):
    return Decimal(str(value))


@tagged('post_install', '-at_install')
class TestDev07QuantityTier(TransactionCase):
    """Quantity tiers and unit normalization. Amounts are company currency.

    The reference figures use the same numbers as the wholesale examples.
    This suite does not activate INR and it does not calculate leakage.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        currency = cls.env.company.currency_id
        cls.company_a = cls.env['res.company'].create({
            'name': 'ABC India',
            'currency_id': currency.id,
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'ABC UAE',
            'currency_id': currency.id,
        })
        cls.owner = cls._make_user('cpla07_owner', 'group_contract_user', cls.company_a)
        cls.other = cls._make_user('cpla07_other', 'group_contract_user', cls.company_a)
        cls.owner_b = cls._make_user('cpla07_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla07_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla07_manager_b', 'group_contract_manager', cls.company_b)
        cls.finance = cls._make_user('cpla07_finance', 'group_finance_manager', cls.company_a)
        cls.finance_b = cls._make_user('cpla07_finance_b', 'group_finance_manager', cls.company_b)
        cls.reviewer = cls._make_user('cpla07_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.auditor = cls._make_user('cpla07_auditor', 'group_internal_auditor', cls.company_a)
        cls.sales = cls._make_user('cpla07_sales', 'group_sales_pricing_reviewer', cls.company_a)
        cls.recovery = cls._make_user('cpla07_recovery', 'group_recovery_operator', cls.company_a)
        cls.admin = cls._make_user('cpla07_admin', 'group_app_admin', cls.company_a)
        cls.combined = cls._make_user(
            'cpla07_combined', 'group_contract_user', cls.company_a,
            extra_groups=('group_finance_reviewer',),
        )
        cls.both = cls._make_user(
            'cpla07_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
            'pricing_date_policy': 'order_confirmation',
            'quantity_basis_policy': 'invoice',
        })
        cls.policy_b = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_b.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'XYZ Manufacturing',
            'is_company': True,
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'UAE Buyer',
            'is_company': True,
            'company_id': cls.company_b.id,
        })
        cls.bearing = cls.env['product.product'].create({
            'name': 'Bearing A',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.bearing_b = cls.env['product.product'].create({
            'name': 'Bearing B',
            'list_price': 8888.0,
            'company_id': False,
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.kg = cls.env.ref('uom.product_uom_kgm')

    @classmethod
    def _make_user(cls, login, xmlid, company, companies=None, extra_groups=()):
        companies = companies or company
        names = ['base.group_user', '%s.%s' % (MODULE, xmlid)]
        names.extend('%s.%s' % (MODULE, extra) for extra in extra_groups)
        return new_test_user(
            cls.env,
            login=login,
            groups=','.join(names),
            password='cpla-test',
            company_id=company.id,
            company_ids=[Command.set(companies.ids)],
        )

    def _env(self, user, company):
        return self.env(user=user, context={
            **self.env.context,
            'allowed_company_ids': [company.id],
        })

    def _today(self):
        return fields.Date.context_today(self.env['cpla.pricing.quantity'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _staff(self, company):
        if company == self.company_a:
            return self.owner, self.manager, self.finance
        return self.owner_b, self.manager_b, self.finance_b

    def _policy(self, company):
        return self.policy_a if company == self.company_a else self.policy_b

    def _draft(self, partner, lines, company=None, owner=None):
        company = company or partner.company_id or self.company_a
        owner = owner or self._staff(company)[0]
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': company.currency_id.id,
            'valid_from': self._on(-30),
            'valid_to': self._on(180),
            'policy_id': self._policy(company).id,
        })
        for product, price in lines:
            env['cpla.customer.contract.line'].create({
                'contract_id': contract.id,
                'product_id': product.id,
                'price_unit': price,
                'uom_id': product.uom_id.id,
            })
        env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': 'signed-agreement.pdf',
            'document_type': 'signed_agreement',
            'source_reference': 'AGR-007',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        return contract

    def _approve_initial(self, contract):
        _owner, manager, _finance = self._staff(contract.company_id)
        env = self._env(manager, contract.company_id)
        return env['cpla.customer.contract.version'].approve_initial(
            env['cpla.customer.contract'].browse(contract.id)
        )

    def _v1(self, partner=None, product=None, price=1000.0, company=None):
        partner = partner or self.partner
        product = product or self.bearing
        company = company or partner.company_id or self.company_a
        contract = self._draft(partner, [(product, price)], company=company)
        contract.action_submit_for_review()
        return self._approve_initial(contract)

    def _box(self, name, factor, product=None):
        uom = self.env['uom.uom'].create({
            'name': name,
            'relative_uom_id': self.unit.id,
            'relative_factor': factor,
        })
        if product is not None:
            product.product_tmpl_id.write({'uom_ids': [Command.link(uom.id)]})
        return uom

    def _add_tiers(self, line, env, specs, basis='sales_order', method='full_volume', return_policy='unconfigured'):
        line.write({
            'tier_method': method,
            'quantity_basis': basis,
            'return_policy': return_policy,
        })
        unit = line.product_id.uom_id
        created = self.env['cpla.customer.contract.version.tier']
        for spec in specs:
            minimum, maximum, price = spec[0], spec[1], spec[2]
            quantity_uom = spec[3] if len(spec) > 3 else unit
            pricing_uom = spec[4] if len(spec) > 4 else unit
            created |= env['cpla.customer.contract.version.tier'].create({
                'version_line_id': line.id,
                'min_quantity': minimum,
                'has_maximum': maximum is not None,
                'max_quantity': maximum or 0.0,
                'quantity_uom_id': quantity_uom.id,
                'price_unit': price,
                'pricing_uom_id': pricing_uom.id,
            })
        return created

    def _standard_specs(self, product=None):
        unit = (product or self.bearing).uom_id
        return (
            (1, 100, 1200.0, unit, unit),
            (100, 500, 1150.0, unit, unit),
            (500, None, 1100.0, unit, unit),
        )

    def _tiered(
        self, basis='sales_order', return_policy='unconfigured', specs=None,
        product=None, partner=None, price=1000.0, company=None, actor=None,
    ):
        product = product or self.bearing
        partner = partner or self.partner
        company = company or partner.company_id or self.company_a
        first = self._v1(partner=partner, product=product, price=price, company=company)
        owner, manager, finance = self._staff(company)
        actor = actor or owner
        env = self._env(actor, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Quantity tiers. Not a retroactive restatement.',
            'effective_from': self._today(),
        })
        self._add_tiers(
            amendment.line_ids, env, specs or self._standard_specs(product),
            basis=basis, return_policy=return_policy,
        )
        env['cpla.customer.contract.version'].browse(amendment.id).action_submit_for_review()
        reviewer = self._env(finance, company)
        record = reviewer['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _resolve(self, user, company, partner, product, **extra):
        payload = {
            'company_id': company.id,
            'partner_id': partner.id if partner else False,
            'product_id': product.id if product else False,
            'pricing_date': extra.pop('pricing_date', self._today()),
        }
        payload.update(extra)
        return self._env(user, company)['cpla.pricing.applicability'].resolve(payload)

    def _qty(self, version, quantity, **extra):
        return self._resolve(
            self.manager, version.company_id, version.partner_id, version.line_ids.product_id,
            quantity=quantity, **extra,
        )

    def _assert_rate(self, result, rate):
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['tier_status'], 'tier_matched')
        self.assertEqual(_dec(result['normalized_unit_price_exact']), _dec(rate))
        self.assertEqual(result['unit_price'], float(rate))
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])

    def _assert_no_price(self, result, *needles):
        self.assertFalse(result['unit_price'])
        self.assertFalse(result['normalized_unit_price'])
        self.assertFalse(result['contract_unit_price'])
        self.assertFalse(result['leakage_amount'])
        text = result['explanation'] or ''
        for needle in needles:
            self.assertNotIn(str(needle), text)

    def test_tier07_t001_manager_creates_a_draft_tier(self):
        first = self._v1()
        env = self._env(self.manager, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        tier = self._add_tiers(amendment.line_ids, env, ((1, 100, 1200.0),))
        self.assertEqual(tier.version_line_id, amendment.line_ids)
        self.assertEqual(tier.price_unit, 1200.0)
        self.assertTrue(tier.quantity_uom_factor)

    def test_tier07_t002_negative_minimum_is_rejected(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((-1, 10, 1200.0),))

    def test_tier07_t003_maximum_must_exceed_minimum(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((10, 10, 1200.0),))

    def test_tier07_t004_overlapping_tiers_are_rejected(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        self._add_tiers(amendment.line_ids, env, ((1, 200, 1200.0),))
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((100, 500, 1150.0),))

    def test_tier07_t005_duplicate_range_is_rejected(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        self._add_tiers(amendment.line_ids, env, ((1, 100, 1200.0),))
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((1, 100, 1100.0),))

    def test_tier07_t006_a_gap_blocks_approval(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Gap check. Not a retroactive restatement.',
            'effective_from': self._today(),
        })
        self._add_tiers(amendment.line_ids, env, ((1, 100, 1200.0), (200, 500, 1150.0)))
        with self.assertRaises(UserError) as caught:
            amendment.action_submit_for_review()
        self.assertIn('gap', str(caught.exception).lower())
        self.assertEqual(amendment.state, 'draft')
        preview = self.env['cpla.pricing.quantity'].evaluate(amendment.line_ids, {'quantity': 150})
        self.assertFalse(preview['unit_price'])

    def test_tier07_t007_full_volume_method_is_stored(self):
        version = self._tiered()
        self.assertEqual(version.line_ids.tier_method, 'full_volume')
        result = self._qty(version, 500)
        self.assertEqual(result['tier_method'], 'full_volume')
        self._assert_rate(result, 1100)

    def test_tier07_t008_graduated_method_is_not_priced_as_full_volume(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.line_ids.write({'tier_method': 'graduated', 'quantity_basis': 'sales_order'})
        preview = env['cpla.pricing.quantity'].evaluate(amendment.line_ids, {'quantity': 500})
        self.assertEqual(preview['quantity_status'], 'unsupported_quantity_policy')
        self.assertFalse(preview['unit_price'])
        with self.assertRaises(UserError) as caught:
            amendment.action_submit_for_review()
        self.assertIn('graduated', str(caught.exception).lower())

    def test_tier07_t009_approval_captures_the_factor(self):
        version = self._tiered()
        tier = version.line_ids.tier_ids.filtered(lambda item: item.min_quantity == 500)
        self.assertTrue(tier.factor_captured_at)
        self.assertGreater(tier.quantity_uom_factor, 0)
        self.assertEqual(version.state, 'approved')

    def test_tier07_t010_approved_tier_cannot_be_edited(self):
        version = self._tiered()
        tier = version.line_ids.tier_ids[:1]
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a).browse_record(tier).write({'price_unit': 1}) if False else tier.with_env(
                self._env(self.owner, self.company_a)
            ).write({'price_unit': 1})
        self.assertNotEqual(tier.price_unit, 1)

    def test_tier07_t011_approved_tier_cannot_be_deleted(self):
        version = self._tiered()
        tier = version.line_ids.tier_ids[:1]
        with self.assertRaises(UserError):
            tier.with_env(self._env(self.owner, self.company_a)).unlink()
        self.assertTrue(tier.exists())

    def test_tier07_t012_tier_company_comes_from_the_version(self):
        version = self._tiered()
        tier = version.line_ids.tier_ids[:1]
        self.assertEqual(tier.company_id, self.company_a)
        self.assertEqual(tier.version_id, version)

    def test_tier07_t013_standalone_price_survives_without_tiers(self):
        version = self._v1(price=1000.0)
        result = self._qty(version, 500)
        self.assertEqual(result['tier_status'], 'base_price_applicable')
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertNotEqual(result['unit_price'], 1100.0)
        self.assertIn('not a qualified tier price', result['explanation'])

    def test_tier07_t014_amendment_keeps_the_previous_tier(self):
        current = self._tiered()
        owner, _manager, finance = self._staff(self.company_a)
        env = self._env(owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(current.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Later tier. Not a retroactive restatement.',
            'effective_from': self._on(1),
        })
        later = amendment.line_ids.tier_ids.filtered(lambda item: not item.has_maximum)
        later.write({'price_unit': 1050.0})
        amendment.action_submit_for_review()
        approved = self._env(finance, self.company_a)['cpla.customer.contract.version'].browse(amendment.id)
        approved.action_approve()
        today = self._qty(current, 500)
        tomorrow = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            quantity=500, pricing_date=self._on(1),
        )
        self._assert_rate(today, 1100)
        self._assert_rate(tomorrow, 1050)
        self.assertEqual(current.line_ids.tier_ids.filtered(lambda item: not item.has_maximum).price_unit, 1100.0)

    def test_tier07_t015_overlap_is_rejected_before_approval(self):
        """Same-transaction overlap rejection. A second database worker was not started."""
        first = self._v1()
        env = self._env(self.manager, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        self._add_tiers(amendment.line_ids, env, ((1, 100, 1200.0),))
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((50, 150, 1100.0),))
        self.assertEqual(len(amendment.line_ids.tier_ids), 1)

    def test_qty07_t001_quantity_1_selects_the_first_tier(self):
        self._assert_rate(self._qty(self._tiered(), 1), 1200)

    def test_qty07_t002_quantity_99_stays_in_the_first_tier(self):
        self._assert_rate(self._qty(self._tiered(), 99), 1200)

    def test_qty07_t003_quantity_100_selects_the_middle_tier(self):
        self._assert_rate(self._qty(self._tiered(), 100), 1150)

    def test_qty07_t004_quantity_499_stays_in_the_middle_tier(self):
        self._assert_rate(self._qty(self._tiered(), 499), 1150)

    def test_qty07_t005_quantity_500_selects_the_open_tier(self):
        self._assert_rate(self._qty(self._tiered(), 500), 1100)

    def test_qty07_t006_quantity_501_stays_in_the_open_tier(self):
        self._assert_rate(self._qty(self._tiered(), 501), 1100)

    def test_qty07_t007_fractional_quantity_is_not_rounded_into_the_next_tier(self):
        result = self._qty(self._tiered(), 99.999)
        self._assert_rate(result, 1200)
        self.assertNotEqual(result['unit_price'], 1150.0)

    def test_qty07_t008_zero_quantity_has_no_tier_price(self):
        result = self._qty(self._tiered(), 0)
        self.assertEqual(result['status'], 'NO_MATCHING_TIER')
        self.assertEqual(result['reason_code'], 'zero_quantity')
        self._assert_no_price(result, 1200, 1150, 1100)

    def test_qty07_t009_negative_quantity_is_not_a_positive_sale(self):
        result = self._qty(self._tiered(), -5)
        self.assertEqual(result['status'], 'NEGATIVE_QUANTITY_REVIEW')
        self._assert_no_price(result, 1100)

    def test_qty07_t010_missing_quantity_is_classified(self):
        version = self._tiered()
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
        )
        self.assertEqual(result['status'], 'MISSING_QUALIFYING_QUANTITY')
        self.assertEqual(result['version_id'], version.id)
        self._assert_no_price(result, 1000, 1100)

    def test_qty07_t011_quantity_unit_must_be_convertible(self):
        result = self._qty(self._tiered(), 100, quantity_uom_id=self.kg.id)
        self.assertEqual(result['status'], 'INCOMPATIBLE_UOM')
        self._assert_no_price(result, 1150)

    def test_qty07_t012_repeated_calls_return_the_same_rate(self):
        version = self._tiered()
        before = self.env['cpla.customer.contract.version.tier'].search_count([])
        first = self._qty(version, 500)
        second = self._qty(version, 500)
        self.assertEqual(first['normalized_unit_price_exact'], second['normalized_unit_price_exact'])
        self.assertEqual(self.env['cpla.customer.contract.version.tier'].search_count([]), before)

    def test_uom07_t001_same_unit_conversion(self):
        service = self.env['cpla.pricing.quantity']
        result = service.convert_quantity(5, 1, 1)
        self.assertTrue(result['ok'])
        self.assertEqual(_dec(result['exact']), _dec(5))

    def test_uom07_t002_compatible_unit_conversion(self):
        result = self.env['cpla.pricing.quantity'].convert_quantity(2, 12, 1)
        self.assertEqual(_dec(result['exact']), _dec(24))

    def test_uom07_t003_box_of_12_normalizes_to_200(self):
        box = self._box('CPLA07 Box 12', 12)
        version = self._tiered(specs=((1, None, 2400.0, self.unit, box),))
        result = self._qty(version, 1, comparison_uom_id=self.unit.id)
        self.assertEqual(_dec(result['contract_unit_price']), _dec(2400))
        self._assert_rate(result, 200)
        self.assertEqual(result['contract_uom_id'], box.id)

    def test_uom07_t004_piece_quantity_is_not_rounded_to_whole_boxes(self):
        box = self._box('CPLA07 Box Exact', 12)
        version = self._tiered(specs=((0.0001, None, 2400.0, self.unit, box),))
        result = self._qty(version, 100, comparison_uom_id=box.id)
        self.assertEqual(_dec(result['normalized_quantity_exact']), _dec(100) / _dec(12))
        self.assertNotEqual(_dec(result['normalized_quantity_exact']), _dec(8))
        self.assertEqual(_dec(result['normalized_unit_price_exact']), _dec(2400))

    def test_uom07_t005_conversion_metadata_names_both_units(self):
        box = self._box('CPLA07 Box Meta', 12)
        version = self._tiered(specs=((1, None, 2400.0, self.unit, box),))
        result = self._qty(version, 12, comparison_uom_id=self.unit.id)
        self.assertEqual(result['contract_uom_id'], box.id)
        self.assertEqual(result['normalized_uom_id'], self.unit.id)
        self.assertTrue(result['conversion_factor_exact'])
        self.assertTrue(result['historical_factor_used'])

    def test_uom07_t006_packaging_factors_are_product_specific(self):
        box_a = self._box('CPLA07 Box A', 12, self.bearing)
        box_b = self._box('CPLA07 Box B', 24, self.bearing_b)
        version_a = self._tiered(product=self.bearing, specs=((1, None, 2400.0, self.unit, box_a),))
        version_b = self._tiered(
            product=self.bearing_b, partner=self.partner, specs=((1, None, 2400.0, self.unit, box_b),),
        )
        price_a = self._qty(version_a, 12, comparison_uom_id=self.unit.id)
        price_b = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing_b,
            quantity=24, comparison_uom_id=self.unit.id,
        )
        self._assert_rate(price_a, 200)
        self._assert_rate(price_b, 100)
        self.assertEqual(version_b.line_ids.product_id, self.bearing_b)

    def test_uom07_t007_another_products_packaging_is_rejected(self):
        box = self._box('CPLA07 Foreign Box', 12, self.bearing_b)
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        with self.assertRaises(ValidationError):
            self._add_tiers(amendment.line_ids, env, ((1, None, 2400.0, self.unit, box),))

    def test_uom07_t008_incompatible_units_are_rejected(self):
        result = self._qty(self._tiered(), 10, comparison_uom_id=self.kg.id)
        self.assertEqual(result['status'], 'INCOMPATIBLE_UOM')
        self._assert_no_price(result, 1200, 1100)

    def test_uom07_t009_zero_factor_is_rejected(self):
        result = self.env['cpla.pricing.quantity'].convert_quantity(10, 0, 1)
        self.assertFalse(result['ok'])
        self.assertFalse(result['amount'])

    def test_uom07_t010_negative_factor_is_rejected(self):
        result = self.env['cpla.pricing.quantity'].convert_price(10, -1, 1)
        self.assertFalse(result['ok'])
        self.assertFalse(result['amount'])

    def test_uom07_t011_and_t012_historical_factor_survives_a_later_change(self):
        box = self._box('CPLA07 Historical Box', 12)
        version = self._tiered(specs=((1, None, 2400.0, self.unit, box),))
        captured = version.line_ids.tier_ids.pricing_uom_factor
        box.write({'relative_factor': 10})
        result = self._qty(version, 12, comparison_uom_id=self.unit.id)
        self.assertEqual(version.line_ids.tier_ids.pricing_uom_factor, captured)
        self._assert_rate(result, 200)
        self.assertNotEqual(result['unit_price'], 240.0)

    def test_uom07_t013_missing_captured_factor_does_not_use_the_live_unit(self):
        version = self._tiered()
        tier = version.line_ids.tier_ids[:1]
        tier._write_multi([{
            'quantity_uom_factor': 0,
            'pricing_uom_factor': 0,
            'product_uom_factor': 0,
        }])
        tier.invalidate_recordset()
        result = self._qty(version, 10)
        self.assertEqual(result['status'], 'MISSING_HISTORICAL_CONVERSION')
        self._assert_no_price(result, 1200, 1100)

    def test_uom07_t014_archived_product_keeps_the_tier(self):
        version = self._tiered()
        self.bearing.active = False
        result = self._qty(version, 500)
        self._assert_rate(result, 1100)
        self.assertEqual(result['product_id'], self.bearing.id)

    def test_uom07_t015_product_packaging_is_not_a_physical_package(self):
        self.assertNotIn('product.packaging', self.env.registry)
        fields_on_tier = self.env['cpla.customer.contract.version.tier']._fields
        self.assertNotIn('package_id', fields_on_tier)
        self.assertNotIn('quant_package_id', fields_on_tier)

    def test_uom07_t016_fractional_conversion_is_stable(self):
        service = self.env['cpla.pricing.quantity']
        first = service.convert_quantity(100, 1, 12)
        second = service.convert_quantity(100, 1, 12)
        self.assertEqual(first['exact'], second['exact'])
        self.assertEqual(_dec(first['exact']), _dec(100) / _dec(12))

    def test_par07_t001_order_quantity_500_selects_the_open_tier(self):
        version = self._tiered(basis='sales_order')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500, billed_quantity=100,
        )
        self._assert_rate(result, 1100)
        self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(500))
        self.assertEqual(_dec(result['billed_quantity_exact']), _dec(100))
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_par07_t002_partial_quantity_keeps_the_order_tier(self):
        version = self._tiered()
        result = self._qty(version, 100, order_quantity=500, billed_quantity=100)
        self._assert_rate(result, 1100)
        self.assertNotEqual(_dec(result['qualified_quantity_exact']), _dec(result['billed_quantity_exact']))

    def test_par07_t003_invoice_quantity_selects_the_invoice_tier(self):
        version = self._tiered(basis='invoice_line')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500, invoice_quantity=100,
        )
        self._assert_rate(result, 1150)
        self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(100))
        self.assertEqual(version.quantity_basis if False else version.line_ids.quantity_basis, 'invoice_line')

    def test_par07_t004_allocations_are_not_added_to_the_order_quantity(self):
        version = self._tiered()
        billed = []
        for allocation in (200, 200, 100):
            result = self._resolve(
                self.manager, self.company_a, self.partner, self.bearing,
                order_quantity=500, billed_quantity=allocation,
            )
            self._assert_rate(result, 1100)
            self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(500))
            billed.append(_dec(result['billed_quantity_exact']))
        self.assertEqual(sum(billed), _dec(500))
        self.assertNotEqual(result['unit_price'], 1100.0 * 500)

    def test_par07_t005_source_reference_does_not_change_the_rate(self):
        version = self._tiered()
        first = self._qty(version, 500, source_reference='SO-1')
        second = self._qty(version, 500, source_reference='SO-2')
        self.assertEqual(first['unit_price'], second['unit_price'])

    def test_par07_t006_unrelated_order_quantity_is_not_substituted(self):
        version = self._tiered(basis='delivery')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500,
        )
        self.assertEqual(result['status'], 'MISSING_QUALIFYING_QUANTITY')
        self.assertEqual(result['version_id'], version.id)
        self._assert_no_price(result, 1100, 1150)

    def test_par07_t007_other_product_quantity_is_not_aggregated(self):
        version = self._tiered()
        result = self._qty(version, 300, other_product_quantity=200)
        self.assertEqual(result['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'product_aggregation_not_approved')
        self._assert_no_price(result, 1100, 1150)
        separate = self._qty(version, 300)
        self._assert_rate(separate, 1150)

    def test_par07_t008_delivery_quantity_is_used_when_the_line_says_so(self):
        version = self._tiered(basis='delivery')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500, delivery_quantity=300,
        )
        self._assert_rate(result, 1150)
        self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(300))
        self.assertEqual(version.line_ids.quantity_basis, 'delivery')

    def test_par07_t009_missing_allocation_is_classified(self):
        version = self._tiered(basis='invoice_line')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            invoice_line_quantities=[100, 100], allocation_unverified=True,
        )
        self.assertEqual(result['status'], 'SOURCE_ALLOCATION_REVIEW_REQUIRED')
        self.assertEqual(result['version_id'], version.id)
        self._assert_no_price(result, 1150)

    def test_par07_t010_return_keeps_the_original_tier_when_locked(self):
        version = self._tiered(return_policy='order_tier_lock')
        result = self._qty(version, 500, returned_quantity=20, billed_quantity=480)
        self._assert_rate(result, 1100)
        self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(500))
        self.assertEqual(version.line_ids.return_policy, 'order_tier_lock')

    def test_par07_t011_net_quantity_retier_uses_480(self):
        version = self._tiered(return_policy='net_quantity')
        result = self._qty(version, 500, returned_quantity=20)
        self._assert_rate(result, 1150)
        self.assertEqual(_dec(result['qualified_quantity_exact']), _dec(480))

    def test_par07_t012_credit_note_is_not_a_new_sale(self):
        version = self._tiered(return_policy='order_tier_lock')
        result = self._qty(version, 500, document_type='credit_note')
        self.assertEqual(result['status'], 'NEGATIVE_QUANTITY_REVIEW')
        self.assertEqual(result['reason_code'], 'credit_note_not_a_sale')
        self.assertEqual(result['version_id'], version.id)
        self._assert_no_price(result, 1100)

    def test_par07_t013_cumulative_volume_is_explicitly_unsupported(self):
        first = self._v1()
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.line_ids.write({'quantity_basis': 'cumulative', 'tier_method': 'full_volume'})
        preview = env['cpla.pricing.quantity'].evaluate(amendment.line_ids, {'quantity': 10000})
        self.assertEqual(preview['status'], 'UNSUPPORTED_QUANTITY_POLICY')
        self.assertFalse(preview['unit_price'])
        with self.assertRaises(UserError):
            amendment.action_submit_for_review()

    def test_his07_t001_and_t002_versions_keep_separate_tiers(self):
        current = self._tiered()
        owner, _manager, finance = self._staff(self.company_a)
        env = self._env(owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(current.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Separate tier version. Not a retroactive restatement.',
            'effective_from': self._on(1),
        })
        amendment.line_ids.tier_ids.filtered(lambda item: not item.has_maximum).write({'price_unit': 900.0})
        amendment.action_submit_for_review()
        self._env(finance, self.company_a)['cpla.customer.contract.version'].browse(amendment.id).action_approve()
        self._assert_rate(self._qty(current, 500), 1100)
        self.assertEqual(
            current.line_ids.tier_ids.filtered(lambda item: not item.has_maximum).price_unit,
            1100.0,
        )

    def test_his07_t003_and_t004_historical_conversion_stays_reproducible(self):
        box = self._box('CPLA07 Frozen Box', 12)
        version = self._tiered(specs=((1, None, 2400.0, self.unit, box),))
        box.write({'relative_factor': 10})
        first = self._qty(version, 12, comparison_uom_id=self.unit.id)
        second = self._qty(version, 12, comparison_uom_id=self.unit.id)
        self.assertEqual(first['normalized_unit_price_exact'], second['normalized_unit_price_exact'])
        self._assert_rate(first, 200)

    def test_his07_t005_tier_reference_is_returned(self):
        version = self._tiered()
        result = self._qty(version, 500)
        tier = self.env['cpla.customer.contract.version.tier'].browse(result['tier_id'])
        self.assertEqual(tier.version_id, version)
        self.assertEqual(tier.price_unit, 1100.0)
        self.assertTrue(version.snapshot_sha256)

    def test_his07_t006_retroactive_amendment_keeps_the_former_tier(self):
        current = self._tiered()
        owner, _manager, _finance = self._staff(self.company_a)
        env = self._env(owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(current.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Attempted restatement.',
            'effective_from': self._on(-1),
        })
        amendment.line_ids.tier_ids.write({'price_unit': 1.0})
        with self.assertRaises(UserError) as caught:
            amendment.action_submit_for_review()
        self.assertIn('earlier authority', str(caught.exception).lower())
        self.assertEqual(amendment.state, 'draft')
        self.assertNotEqual(amendment.state, 'approved')
        self._assert_rate(self._qty(current, 99), 1200)
        self.assertEqual(
            current.line_ids.tier_ids.filtered(lambda item: item.min_quantity == 1).price_unit,
            1200.0,
        )

    def test_his07_t007_live_policy_does_not_replace_the_line_basis(self):
        version = self._tiered(basis='sales_order')
        self.policy_a.write({
            'quantity_basis_policy': 'invoice',
            'change_reason': 'Candidate only. Not an operational quantity rule.',
        })
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500, invoice_quantity=100,
        )
        self._assert_rate(result, 1100)
        self.assertEqual(version.line_ids.quantity_basis, 'sales_order')
        self.assertEqual(self.policy_a.quantity_basis_policy, 'invoice')
        self.assertFalse(result['policy_operationally_approved'])

    def test_his07_t008_repeated_normalization_matches(self):
        box = self._box('CPLA07 Repeat Box', 12)
        version = self._tiered(specs=((1, None, 2400.0, self.unit, box),))
        first = self._qty(version, 100, comparison_uom_id=self.unit.id)
        second = self._qty(version, 100, comparison_uom_id=self.unit.id)
        self.assertEqual(first['normalized_unit_price_exact'], second['normalized_unit_price_exact'])
        self._assert_rate(second, 200)

    def test_his07_t009_approved_line_write_is_rejected(self):
        version = self._tiered()
        with self.assertRaises(UserError):
            version.line_ids.with_env(self._env(self.owner, self.company_a)).write({'price_unit': 5})
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_his07_t010_approved_tier_unlink_is_rejected(self):
        version = self._tiered()
        with self.assertRaises(UserError):
            version.line_ids.tier_ids.with_env(self._env(self.manager, self.company_a)).unlink()
        self.assertEqual(len(version.line_ids.tier_ids), 3)

    def test_sec07_t001_manager_draft_tier_is_allowed(self):
        self.test_tier07_t001_manager_creates_a_draft_tier()

    def test_sec07_t002_contract_user_cannot_change_an_approved_tier(self):
        self.test_tier07_t010_approved_tier_cannot_be_edited()

    def test_sec07_t003_finance_reviewer_cannot_change_quantity_terms(self):
        version = self._tiered()
        reviewer = self._env(self.reviewer, self.company_a)
        with self.assertRaises(AccessError):
            reviewer['cpla.company.policy'].browse(self.policy_a.id).write({
                'quantity_basis_policy': 'sales_order',
            })
        with self.assertRaises(AccessError):
            reviewer['cpla.customer.contract.version.line'].browse(version.line_ids.id).write({
                'quantity_basis': 'invoice_line',
            })

    def test_sec07_t004_company_a_cannot_read_company_b_tiers(self):
        foreign = self._tiered(company=self.company_b, partner=self.partner_b)
        outsider = self._env(self.manager, self.company_a)
        self.assertFalse(outsider['cpla.customer.contract.version.tier'].search([
            ('id', 'in', foreign.line_ids.tier_ids.ids),
        ]))
        grouped = outsider['cpla.customer.contract.version.tier']._read_group(
            [('company_id', '=', self.company_b.id)],
            ['company_id'],
            ['price_unit:sum'],
        )
        self.assertFalse(grouped)

    def test_sec07_t005_cross_company_tier_link_is_rejected(self):
        foreign = self._v1(partner=self.partner_b, company=self.company_b)
        env = self._env(self.owner_b, self.company_b)
        amendment = env['cpla.customer.contract.version'].browse(foreign.id).create_amendment()
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)['cpla.customer.contract.version.tier'].create({
                'version_line_id': amendment.line_ids.id,
                'min_quantity': 1,
                'has_maximum': False,
                'quantity_uom_id': self.unit.id,
                'price_unit': 1100,
                'pricing_uom_id': self.unit.id,
            })

    def test_sec07_t006_sales_user_cannot_create_a_tier(self):
        version = self._tiered()
        with self.assertRaises(AccessError):
            self._env(self.sales, self.company_a)['cpla.customer.contract.version.tier'].create({
                'version_line_id': version.line_ids.id,
                'min_quantity': 1,
                'price_unit': 1,
                'quantity_uom_id': self.unit.id,
                'pricing_uom_id': self.unit.id,
            })

    def test_sec07_t007_approved_child_tier_mutation_is_blocked(self):
        version = self._tiered()
        with self.assertRaises(UserError):
            version.line_ids.with_env(self._env(self.manager, self.company_a)).write({
                'tier_ids': [Command.update(version.line_ids.tier_ids[:1].id, {'price_unit': 2})],
            })
        self.assertNotIn(2.0, version.line_ids.tier_ids.mapped('price_unit'))

    def test_sec07_t008_unauthorized_resolve_does_not_expose_the_rate(self):
        self._tiered()
        with self.assertRaises(AccessError) as caught:
            self._resolve(self.sales, self.company_a, self.partner, self.bearing, quantity=500)
        self.assertNotIn('1100', str(caught.exception))
        with self.assertRaises(AccessError) as recovery:
            self._resolve(self.recovery, self.company_a, self.partner, self.bearing, quantity=500)
        self.assertNotIn('1100', str(recovery.exception))

    def test_sec07_t009_other_company_tier_export_is_denied(self):
        foreign = self._tiered(company=self.company_b, partner=self.partner_b, price=1800.0)
        outsider = self._env(self.manager, self.company_a)
        with self.assertRaises(UserError) as caught:
            outsider['cpla.customer.contract.version.tier'].browse(
                foreign.line_ids.tier_ids.ids
            ).export_data(['price_unit'])
        self.assertNotIn('1800', str(caught.exception))
        self.assertNotIn('1100', str(caught.exception))

    def test_sec07_t010_multi_company_user_stays_inside_the_requested_company(self):
        self._tiered()
        foreign = self._tiered(company=self.company_b, partner=self.partner_b)
        result = self._env(self.both, self.company_a)['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
            'quantity': 500,
        })
        self._assert_rate(result, 1100)
        self.assertNotEqual(result['version_id'], foreign.id)

    def test_sec07_t011_combined_roles_cannot_edit_an_approved_tier(self):
        version = self._tiered()
        with self.assertRaises(UserError):
            version.line_ids.tier_ids[:1].with_env(
                self._env(self.combined, self.company_a)
            ).write({'price_unit': 3})
        self.assertNotEqual(version.line_ids.tier_ids[:1].price_unit, 3)

    def test_sec07_t012_quantity_service_does_not_grant_a_hidden_rate(self):
        version = self._tiered()
        with self.assertRaises(AccessError) as caught:
            self._env(self.admin, self.company_a)['cpla.pricing.quantity'].evaluate(
                version.line_ids, {'quantity': 500},
            )
        self.assertNotIn('1100', str(caught.exception))

    def test_reg07_t001_and_t002_version_is_loaded(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')

    def test_reg07_t003_and_t004_headers_and_versions_remain(self):
        version = self._v1(price=1000.0)
        self.assertEqual(version.contract_id.state, 'ready_for_review')
        self.assertNotIn('approved', dict(version.contract_id._fields['state'].selection))
        self.assertEqual(version.state, 'approved')
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_reg07_t005_approved_price_is_not_rewritten_by_quantity(self):
        version = self._tiered()
        before = version.line_ids.price_unit
        self._qty(version, 500)
        self.assertEqual(version.line_ids.price_unit, before)

    def test_reg07_t006_and_t007_resolver_still_selects_one_authority(self):
        version = self._v1(price=1000.0)
        result = self._resolve(self.manager, self.company_a, self.partner, self.bearing)
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self._v1(price=1400.0)
        conflict = self._resolve(self.manager, self.company_a, self.partner, self.bearing)
        self.assertEqual(conflict['status'], 'CONFLICT_REVIEW_REQUIRED')
        self._assert_no_price(conflict, 1000, 1400)

    def test_reg07_t008_and_t009_security_and_views_load(self):
        self.assertTrue(self.env.ref('%s.group_contract_manager' % MODULE))
        form = self.env['cpla.customer.contract.version'].get_view(view_type='form')
        self.assertIn('Quantity Tiers', form['arch'])
        check = self.env['cpla.pricing.applicability.check'].get_view(view_type='form')
        self.assertIn('comparison_uom_id', check['arch'])
        self.assertIn('not an approved price', check['arch'])
        self.assertNotIn('Run Invoice Audit', check['arch'])

    def test_reg07_t010_prior_suites_remain_imported(self):
        from odoo.addons.contract_price_leakage_auditor.tests import (
            test_company_policy,
            test_contract_version,
            test_customer_contract,
            test_foundation_smoke,
            test_pricing_applicability,
            test_security_foundation,
        )
        self.assertTrue(test_pricing_applicability.TestDev06PricingApplicability)
        self.assertTrue(test_contract_version.TestDev05ContractVersion)
        self.assertTrue(test_customer_contract.TestDev04CustomerContract)
        self.assertTrue(test_company_policy.TestDev03CompanyPolicy)
        self.assertTrue(test_foundation_smoke.TestDev01Foundation)
        self.assertTrue(test_security_foundation.TestDev02Security)

    def test_reg07_t011_t012_and_t013_no_invoice_recovery_or_cron(self):
        version = self._tiered()
        before = self.env['account.move'].search_count([]) if 'account.move' in self.env.registry else None
        self._qty(version, 500)
        if before is not None:
            self.assertEqual(self.env['account.move'].search_count([]), before)
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        self.assertFalse(any(
            name.startswith('cpla.audit')
            for name in self.env.registry
        ))
        if 'cpla.recovery.request' in self.env.registry:
            self.assertFalse(self.env['cpla.recovery.request'].search_count([]))
        self.assertFalse(self.env['ir.cron'].search([
            ('cron_name', 'ilike', 'quantity'),
        ]))

    def test_qt_ref_001_boundaries(self):
        version = self._tiered()
        self._assert_rate(self._qty(version, 99), 1200)
        self._assert_rate(self._qty(version, 100), 1150)
        self._assert_rate(self._qty(version, 499), 1150)
        self._assert_rate(self._qty(version, 500), 1100)

    def test_qt_ref_002_sales_order_lock_for_five_partials(self):
        self._tiered()
        for _index in range(5):
            result = self._resolve(
                self.manager, self.company_a, self.partner, self.bearing,
                order_quantity=500, billed_quantity=100,
            )
            self._assert_rate(result, 1100)
            self.assertEqual(_dec(result['billed_quantity_exact']), _dec(100))

    def test_qt_ref_003_invoice_basis(self):
        self._tiered(basis='invoice_line')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            order_quantity=500, invoice_quantity=100,
        )
        self._assert_rate(result, 1150)

    def test_qt_ref_004_per_box(self):
        self.test_uom07_t003_box_of_12_normalizes_to_200()

    def test_qt_ref_005_product_specific_boxes(self):
        self.test_uom07_t006_packaging_factors_are_product_specific()

    def test_qt_ref_006_historical_packaging_change(self):
        self.test_uom07_t011_and_t012_historical_factor_survives_a_later_change()

    def test_qt_ref_007_fractional_boundary(self):
        self.test_qty07_t007_fractional_quantity_is_not_rounded_into_the_next_tier()

    def test_qt_ref_008_incompatible_kilogram(self):
        self.test_uom07_t008_incompatible_units_are_rejected()

    def test_qt_ref_009_partial_allocations(self):
        self.test_par07_t004_allocations_are_not_added_to_the_order_quantity()

    def test_qt_ref_010_return_tier_lock(self):
        self.test_par07_t010_return_keeps_the_original_tier_when_locked()

    def test_qt_ref_011_net_retier(self):
        self.test_par07_t011_net_quantity_retier_uses_480()

    def test_qt_ref_012_missing_order_quantity(self):
        version = self._tiered(basis='sales_order')
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            invoice_quantity=100,
        )
        self.assertEqual(result['status'], 'MISSING_QUALIFYING_QUANTITY')
        self.assertEqual(result['version_id'], version.id)
        self._assert_no_price(result, 1150, 1100)

    def test_qt_ref_013_overlap(self):
        self.test_tier07_t004_overlapping_tiers_are_rejected()

    def test_qt_ref_014_gap(self):
        self.test_tier07_t006_a_gap_blocks_approval()

    def test_qt_ref_015_mixed_products_stay_separate(self):
        self._tiered(product=self.bearing)
        self._tiered(product=self.bearing_b)
        bearing_a = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing, quantity=300,
        )
        bearing_b = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing_b, quantity=200,
        )
        self._assert_rate(bearing_a, 1150)
        self._assert_rate(bearing_b, 1150)
        self.assertNotEqual(bearing_a['unit_price'], 1100.0)

    def test_det07_lookup_stays_under_the_ceiling(self):
        version = self._tiered()
        for index in range(8):
            partner = self.env['res.partner'].create({
                'name': 'Qty Buyer %s' % index,
                'is_company': True,
                'company_id': self.company_a.id,
            })
            self._tiered(partner=partner)
        import time
        started = time.perf_counter()
        result = self._qty(version, 500)
        elapsed = time.perf_counter() - started
        self._assert_rate(result, 1100)
        self.assertLess(elapsed, 5.0, 'measured_seconds=%.4f' % elapsed)
