# Copyright 2020 Camptocamp SA
# Copyright 2020 ForgeFlow, S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from datetime import datetime, time, date
from dateutil.relativedelta import relativedelta
from pytz import timezone, UTC

from odoo import _, api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    product_packaging = fields.Many2one(
        comodel_name="product.packaging",
        string="Package",
        default=False,
        check_company=True,
    )
    product_packaging_qty = fields.Float(
        string="Package quantity",
        compute="_compute_product_packaging_qty",
        inverse="_inverse_product_packaging_qty",
        digits="Product Unit of Measure",
    )

    date_planned = fields.Datetime(string='Delivery Date', index=True,
                                   help="Delivery date expected from vendor. This date respectively defaults to vendor pricelist lead time then today's date.")

    @api.depends(
        "product_qty", "product_uom_id", "product_packaging", "product_packaging.qty"
    )
    def _compute_product_packaging_qty(self):
        for pol in self:
            if (
                not pol.product_packaging
                or pol.product_qty == 0
                or pol.product_packaging.qty == 0
            ):
                pol.product_packaging_qty = 0
                continue
            # Consider uom
            if pol.product_id.uom_id != pol.product_uom_id:
                product_qty = pol.product_uom_id._compute_quantity(
                    pol.product_qty, pol.product_id.uom_id
                )
            else:
                product_qty = pol.product_qty
            pol.product_packaging_qty = product_qty / pol.product_packaging.qty

    def _prepare_product_packaging_qty_values(self):
        return {
            "product_qty": self.product_packaging.qty * self.product_packaging_qty,
            "product_uom_id": self.product_packaging.product_uom_id.id,
        }

    def _inverse_product_packaging_qty(self):
        for pol in self:
            if pol.product_packaging_qty and not pol.product_packaging:
                raise UserError(
                    _(
                        "You must define a package before setting a quantity "
                        "of said package."
                    )
                )
            if pol.product_packaging and pol.product_packaging.qty == 0:
                raise UserError(
                    _("Please select a packaging with a quantity bigger than 0")
                )
            if pol.product_packaging and pol.product_packaging_qty:
                pol.write(pol._prepare_product_packaging_qty_values())

    @api.onchange("product_packaging")
    def _onchange_product_packaging(self):
        if self.product_packaging:
            self.update(
                {
                    "product_packaging_qty": 1,
                    "product_qty": self.product_packaging.qty,
                    "product_uom_id": self.product_id.uom_id,
                }
            )
        else:
            self.update({"product_packaging_qty": 0})
        if self.product_packaging:
            return self._check_package()

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_packaging:
            self.product_packaging = ''
        else:
            if self.product_id:
                pack = self.env["product.packaging"].search([("product_id","=",self.product_id.id)], limit=1)
                if pack:
                    self.product_packaging = pack.id

    @api.onchange("product_packaging_qty")
    def _onchange_product_packaging_qty(self):
        if self.product_packaging_qty and self.product_packaging:
            self.update(self._prepare_product_packaging_qty_values())

    def _convert_to_middle_of_day(self, date):
        """Return a datetime which is the noon of the input date(time) according
        to order user's time zone, convert to UTC time.
        """
        tz = timezone(
            self.request_id.requested_by.tz or self.company_id.partner_id.tz or 'UTC')
        # date = date.astimezone(tz) # date is UTC, applying the offset could change the day
        return tz.localize(datetime.combine(date, time(12))).astimezone(UTC).replace(tzinfo=None)

    @api.model
    def _get_date_planned(self, seller, pr=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.
           :param Model seller: used to fetch the delivery delay (if no seller
                                is provided, the delay is 0)
           :param Model po: purchase.order, necessary only if the PO line is
                            not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        date_start = pr.date_start if pr else self.request_id.date_start
        if date_start:
            date_planned = date_start + \
                relativedelta(days=seller.delay if seller else 0)
        else:
            date_planned = datetime.today() + relativedelta(days=seller.delay if seller else 0)
        return self._convert_to_middle_of_day(date_planned)

    def _onchange_quantity_purchase(self):
        if not self.product_id:
            return
        params = {'request_id': self.request_id}
        seller = self.product_id._select_seller(
            # partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.request_id.date_start,
            uom_id=self.product_uom_id,
            params=params)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(
                seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.onchange("product_qty", "product_uom_id")
    def _onchange_quantity(self):
        res = self._onchange_quantity_purchase()
        if not res:
            res = self._check_package()
        return res

    def _check_package(self):
        default_uom = self.product_id.uom_id
        pack = self.product_packaging
        qty = self.product_qty
        q = default_uom._compute_quantity(pack.qty, self.product_uom_id)
        if qty and q and round(qty % q, 2):
            newqty = qty - (qty % q) + q
            return {
                "warning": {
                    "title": _("Warning"),
                    "message": _(
                        "This product is packaged by %.2f %s. You should sell %.2f %s."
                    )
                    % (pack.qty, default_uom.name, newqty, self.product_uom_id.name),
                },
            }
        return {}

    @api.model
    def _prepare_purchase_order_line_from_procurement(
        self, product_id, product_qty, product_uom_id, company_id, values, po
    ):
        # For new PO lines we set the product packaging if present in
        # the procurement values.
        vals = super()._prepare_purchase_order_line_from_procurement(
            product_id, product_qty, product_uom_id, company_id, values, po
        )
        if values.get("product_packaging_id"):
            vals["product_packaging"] = values.get("product_packaging_id").id
        return vals
