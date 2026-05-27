# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from bpy.types import Panel, UILayout
from .panel import POLYGONINGENIEUR_panel
from ..operators.operator_website import CHAT_COMPANION_OT_website
from ..properties.addon_preferences import ChatCompanionPreferences
from ..utils import cc_globals
from .. import __package__ as base_package


class CHAT_COMPANION_PT_links(POLYGONINGENIEUR_panel, Panel):
    bl_idname = "CHAT_COMPANION_PT_links"
    bl_label = "Links"
    bl_order = 4

    def draw_header(self, context):
        self.layout.label(text="", icon="URL")

    def draw(self, context):
        pcoll = cc_globals.preview_collections["main"]
        addon_preferences: ChatCompanionPreferences = context.preferences.addons[
            base_package
        ].preferences

        layout: UILayout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        links_container: UILayout = layout.column(align=True)
        # ! open ai
        if addon_preferences.llm_organization == "openai":
            links_container.label(
                text="OpenAI", icon_value=pcoll["openai_icon"].icon_id
            )

            # Pricing button
            princing_link = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Pricing",
                icon_value=pcoll["money_icon"].icon_id,
            )
            princing_link.url = "https://openai.com/pricing"

            # api key and usage website
            usage_link: CHAT_COMPANION_OT_website = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Your Usage Summary",
                icon="USER",
            )
            usage_link.url = "https://platform.openai.com/account/usage"

            # status button
            server_status_link = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Server Status",
                icon="RESTRICT_VIEW_OFF",
            )
            server_status_link.url = "https://status.openai.com/"

        # ! deepseek
        elif addon_preferences.llm_organization == "deepseek":
            links_container.label(text="DeepSeek", icon="OUTLINER_OB_LIGHT")

            pricing_link: CHAT_COMPANION_OT_website = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Pricing",
                icon_value=pcoll["money_icon"].icon_id,
            )
            pricing_link.url = "https://api-docs.deepseek.com/quick_start/pricing"
            docs_link: CHAT_COMPANION_OT_website = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="API Docs",
                icon="QUESTION",
            )
            docs_link.url = "https://api-docs.deepseek.com/api/create-chat-completion"

        # ! anthropic
        elif addon_preferences.llm_organization == "anthropic":
            links_container.label(
                text="Anthropic", icon_value=pcoll["anthropic_icon"].icon_id
            )

            pricing_link: CHAT_COMPANION_OT_website = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="Pricing",
                icon_value=pcoll["money_icon"].icon_id,
            )
            pricing_link.url = "https://www.anthropic.com/pricing"
            docs_link: CHAT_COMPANION_OT_website = links_container.operator(
                operator=CHAT_COMPANION_OT_website.bl_idname,
                text="API Docs",
                icon="QUESTION",
            )
            docs_link.url = "https://docs.anthropic.com/en/api"
