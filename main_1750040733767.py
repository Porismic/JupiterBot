
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import math
import asyncio

# --------- Config -----------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = 1362531923586453678  # Your guild ID here
TIER_CHANNEL_ID = 1362836497060855959  # Tier list channel ID

# Auction configuration
AUCTION_FORUM_CHANNEL_ID = 1362896002981433354  # Replace with your auction forum channel ID
BIDDER_ROLE_ID = 1362851306330652842  # Replace with bidder role ID
BUYER_ROLE_ID = 1362851277222056108  # Replace with buyer role ID

# Role permissions - Add your role IDs here for access control
STAFF_ROLES = [
    1362545929038594118,  # Replace with actual staff role ID
    1362546172429996323,  # Replace with actual admin role ID
    # Add more role IDs as needed
]

# Default embed color
DEFAULT_EMBED_COLOR = 0x680da8

# Tier colors for embeds
TIER_COLORS = {
    "s": 0xFFD700,  # Gold
    "a": 0xC0C0C0,  # Silver
    "b": 0xCD7F32,  # Bronze
    "c": 0x3498DB,  # Blue
    "d": 0x95A5A6,  # Gray
}

# Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --------- Data loading & saving -----------

def load_json(file_name):
    if os.path.isfile(file_name):
        with open(file_name, "r") as f:
            return json.load(f)
    return {}

tier_data = load_json("tierlist.json")
member_stats = load_json("member_stats.json")
shops_data = load_json("shops.json")  # Multiple shops
user_balances = load_json("balances.json")
user_inventories = load_json("inventories.json")  # User inventories
reaction_roles = load_json("reaction_roles.json")
sticky_messages = load_json("sticky_messages.json")  # Sticky message tracking
server_settings = load_json("server_settings.json")  # Server configuration
verification_data = load_json("verification.json")  # Verification system
user_profiles = load_json("user_profiles.json")  # User profiles
giveaways_data = load_json("giveaways.json")  # Giveaways
auction_data = load_json("auctions.json")  # Auction data

def save_json(file_name, data):
    with open(file_name, "w") as f:
        json.dump(data, f, indent=2)

def save_all():
    save_json("tierlist.json", tier_data)
    save_json("member_stats.json", member_stats)
    save_json("shops.json", shops_data)
    save_json("balances.json", user_balances)
    save_json("inventories.json", user_inventories)
    save_json("reaction_roles.json", reaction_roles)
    save_json("sticky_messages.json", sticky_messages)
    save_json("server_settings.json", server_settings)
    save_json("verification.json", verification_data)
    save_json("auctions.json", auction_data)
    save_json("user_profiles.json", user_profiles)
    save_json("giveaways.json", giveaways_data)

# --------- Helper Functions -----------

def has_staff_role(interaction: discord.Interaction):
    user_role_ids = [role.id for role in interaction.user.roles]
    return any(role_id in STAFF_ROLES for role_id in user_role_ids)

def get_currency_symbol():
    return server_settings.get("currency_symbol", "$")

def get_color_for_tier(tier: str):
    return TIER_COLORS.get(tier.lower(), DEFAULT_EMBED_COLOR)

def calculate_level(xp: int):
    return int(math.sqrt(xp / 100)) if xp >= 0 else 0

def calculate_xp_for_level(level: int):
    return level * level * 100

def get_level_progress_bar(current_xp: int, level: int):
    current_level_xp = calculate_xp_for_level(level)
    next_level_xp = calculate_xp_for_level(level + 1)
    
    if level == 0:
        progress = current_xp / next_level_xp
        current_progress = current_xp
        needed_for_next = next_level_xp
    else:
        progress = (current_xp - current_level_xp) / (next_level_xp - current_level_xp)
        current_progress = current_xp - current_level_xp
        needed_for_next = next_level_xp - current_level_xp
    
    bar_length = 10
    filled_length = int(bar_length * progress)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    
    return f"{bar} {current_progress}/{needed_for_next} XP"

def get_sorted_leaderboard():
    return sorted(
        member_stats.items(),
        key=lambda x: calculate_level(x[1].get("xp", 0)),
        reverse=True,
    )

def build_level_leaderboard_embed(page: int = 0, per_page: int = 15):
    sorted_list = get_sorted_leaderboard()
    total_pages = max(1, (len(sorted_list) + per_page -1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    sliced = sorted_list[start:end]

    embed = discord.Embed(
        title=f"Level Leaderboard (Page {page+1}/{total_pages})",
        color=DEFAULT_EMBED_COLOR,
    )

    if not sliced:
        embed.description = "No data to display."
        return embed

    for rank, (user_id, data) in enumerate(sliced, start=start + 1):
        level = calculate_level(data.get("xp", 0))
        xp = data.get("xp", 0)
        progress_bar = get_level_progress_bar(xp, level)
        embed.add_field(name=f"{rank}. <@{user_id}>", value=f"Level {level}\n{progress_bar}", inline=False)

    return embed

def build_level_embed(user: discord.User):
    data = member_stats.get(str(user.id), {})
    level = calculate_level(data.get("xp", 0))
    xp = data.get("xp", 0)
    progress_bar = get_level_progress_bar(xp, level)
    
    embed = discord.Embed(
        title=f"{user.display_name}'s Level",
        color=DEFAULT_EMBED_COLOR,
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="Level", value=f"Level {level}", inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="Progress to Next Level", value=progress_bar, inline=False)
    
    return embed

def build_message_embed(user: discord.User, message_type: str):
    data = member_stats.get(str(user.id), {})
    messages = data.get(f"{message_type}_messages", 0)
    
    embed = discord.Embed(
        title=f"{user.display_name}'s {message_type.replace('_', ' ').title()} Messages",
        color=DEFAULT_EMBED_COLOR,
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="Messages", value=str(messages), inline=True)
    
    return embed

def ensure_user_in_stats(user_id: str):
    if user_id not in member_stats:
        member_stats[user_id] = {
            "xp": 0,
            "daily_messages": 0,
            "weekly_messages": 0,
            "monthly_messages": 0,
            "all_time_messages": 0,
        }
    if user_id not in user_balances:
        user_balances[user_id] = 0
    if user_id not in user_inventories:
        user_inventories[user_id] = {}

# --------- Views for Pagination -----------

class LevelLeaderboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.page = 0

    async def update_message(self, interaction: discord.Interaction):
        embed = build_level_leaderboard_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        sorted_list = get_sorted_leaderboard()
        max_page = max(0, (len(sorted_list) - 1) // 15)
        if self.page < max_page:
            self.page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

# --------- Guild Restriction Check -----------

def guild_only():
    def predicate(interaction: discord.Interaction):
        return interaction.guild and interaction.guild.id == GUILD_ID
    return app_commands.check(predicate)

# --------- Server Settings Commands -----------

@tree.command(name="set_currency", description="Set the server's currency symbol", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    symbol_type="Type of currency symbol",
    symbol="The symbol to use (emoji or text/unicode)"
)
@app_commands.choices(symbol_type=[
    app_commands.Choice(name="Emoji", value="emoji"),
    app_commands.Choice(name="Text/Unicode", value="text"),
])
async def set_currency(interaction: discord.Interaction, symbol_type: app_commands.Choice[str], symbol: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    server_settings["currency_symbol"] = symbol
    save_json("server_settings.json", server_settings)
    await interaction.response.send_message(f"Currency symbol set to: {symbol}")

@tree.command(name="set_levelup_channel", description="Set the level up notification channel", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(channel="Channel for level up notifications")
async def set_levelup_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    server_settings["levelup_channel_id"] = channel.id
    save_json("server_settings.json", server_settings)
    await interaction.response.send_message(f"Level up notifications will be sent to {channel.mention}")

# --------- Level Commands -----------

@tree.command(name="level", description="Show your level", guild=discord.Object(id=GUILD_ID))
@guild_only()
async def level_self(interaction: discord.Interaction):
    embed = build_level_embed(interaction.user)
    await interaction.response.send_message(embed=embed)

@tree.command(name="level_user", description="Show another user's level", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(user="User to check")
async def level_user(interaction: discord.Interaction, user: discord.Member):
    embed = build_level_embed(user)
    await interaction.response.send_message(embed=embed)

@tree.command(name="level_leaderboard", description="Show the level leaderboard", guild=discord.Object(id=GUILD_ID))
@guild_only()
async def level_leaderboard(interaction: discord.Interaction):
    view = LevelLeaderboardView()
    embed = build_level_leaderboard_embed(0)
    await interaction.response.send_message(embed=embed, view=view)

# --------- Message Commands -----------

@tree.command(name="messages", description="Show your message statistics", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(message_type="Type of messages to display")
@app_commands.choices(message_type=[
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
    app_commands.Choice(name="All Time", value="all_time"),
])
async def messages_self(interaction: discord.Interaction, message_type: app_commands.Choice[str]):
    embed = build_message_embed(interaction.user, message_type.value)
    await interaction.response.send_message(embed=embed)

@tree.command(name="messages_user", description="Show another user's message statistics", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    message_type="Type of messages to display",
    user="User to check"
)
@app_commands.choices(message_type=[
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Monthly", value="monthly"),
    app_commands.Choice(name="All Time", value="all_time"),
])
async def messages_user(interaction: discord.Interaction, message_type: app_commands.Choice[str], user: discord.Member):
    embed = build_message_embed(user, message_type.value)
    await interaction.response.send_message(embed=embed)

# --------- Verification System -----------

@tree.command(name="verification_setup", description="Set up verification system", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    verification_word="Word that users must type to verify",
    verified_role="Role to give when verified",
    verification_channel="Channel where verification will be monitored"
)
async def verification_setup(interaction: discord.Interaction, verification_word: str, verified_role: discord.Role, verification_channel: discord.TextChannel):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    verification_data["word"] = verification_word.lower()
    verification_data["role_id"] = verified_role.id
    verification_data["channel_id"] = verification_channel.id
    save_json("verification.json", verification_data)
    await interaction.response.send_message(f"Verification system set up! Users must type '{verification_word}' in {verification_channel.mention} to get the {verified_role.name} role.")

# --------- Sticky Messages -----------

@tree.command(name="sticky_create", description="Create a sticky message", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    channel="Channel for the sticky message",
    message_type="Type of sticky message",
    title="Title of the sticky message (for embeds)",
    description="Description/content of the sticky message",
    image_url="Image URL (optional)"
)
@app_commands.choices(message_type=[
    app_commands.Choice(name="Embed", value="embed"),
    app_commands.Choice(name="Regular Message", value="message"),
])
async def sticky_create(interaction: discord.Interaction, channel: discord.TextChannel, message_type: app_commands.Choice[str], title: str, description: str, image_url: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if message_type.value == "embed":
        embed = discord.Embed(title=title, description=description, color=DEFAULT_EMBED_COLOR)
        if image_url:
            embed.set_image(url=image_url)
        message = await channel.send(embed=embed)
    else:
        content = f"**{title}**\n{description}"
        if image_url:
            content += f"\n{image_url}"
        message = await channel.send(content)
    
    sticky_messages[str(channel.id)] = {
        "message_id": message.id,
        "type": message_type.value,
        "title": title,
        "description": description,
        "image_url": image_url
    }
    save_json("sticky_messages.json", sticky_messages)
    await interaction.response.send_message(f"Sticky {message_type.value} created in {channel.mention}")

@tree.command(name="sticky_edit", description="Edit a sticky message", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    channel="Channel with the sticky message",
    title="New title",
    description="New description/content",
    image_url="New image URL (optional)"
)
async def sticky_edit(interaction: discord.Interaction, channel: discord.TextChannel, title: str = None, description: str = None, image_url: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    channel_id = str(channel.id)
    if channel_id not in sticky_messages:
        await interaction.response.send_message("No sticky message found in this channel.")
        return
    
    sticky_data = sticky_messages[channel_id]
    
    # Update data
    if title:
        sticky_data["title"] = title
    if description:
        sticky_data["description"] = description
    if image_url is not None:
        sticky_data["image_url"] = image_url
    
    # Delete old message and create new one
    try:
        old_message = await channel.fetch_message(sticky_data["message_id"])
        await old_message.delete()
    except:
        pass
    
    if sticky_data["type"] == "embed":
        embed = discord.Embed(title=sticky_data["title"], description=sticky_data["description"], color=DEFAULT_EMBED_COLOR)
        if sticky_data.get("image_url"):
            embed.set_image(url=sticky_data["image_url"])
        new_message = await channel.send(embed=embed)
    else:
        content = f"**{sticky_data['title']}**\n{sticky_data['description']}"
        if sticky_data.get("image_url"):
            content += f"\n{sticky_data['image_url']}"
        new_message = await channel.send(content)
    
    sticky_data["message_id"] = new_message.id
    save_json("sticky_messages.json", sticky_messages)
    await interaction.response.send_message(f"Sticky message updated in {channel.mention}")

@tree.command(name="sticky_delete", description="Delete a sticky message", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(channel="Channel with the sticky message")
async def sticky_delete(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    channel_id = str(channel.id)
    if channel_id not in sticky_messages:
        await interaction.response.send_message("No sticky message found in this channel.")
        return
    
    try:
        message = await channel.fetch_message(sticky_messages[channel_id]["message_id"])
        await message.delete()
    except:
        pass
    
    del sticky_messages[channel_id]
    save_json("sticky_messages.json", sticky_messages)
    await interaction.response.send_message(f"Sticky message deleted from {channel.mention}")

# --------- Shop System -----------

@tree.command(name="shop_create", description="Create a new shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(shop_name="Name of the shop", description="Shop description")
async def shop_create(interaction: discord.Interaction, shop_name: str, description: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    if shop_key in shops_data:
        await interaction.response.send_message("A shop with this name already exists.")
        return
    
    shops_data[shop_key] = {
        "name": shop_name,
        "description": description,
        "items": {}
    }
    save_json("shops.json", shops_data)
    await interaction.response.send_message(f"Shop '{shop_name}' created successfully!")

@tree.command(name="shop_add", description="Add an item to a shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    shop_name="Name of the shop",
    item="Item name",
    price="Price in currency",
    description="Item description"
)
async def shop_add(interaction: discord.Interaction, shop_name: str, item: str, price: int, description: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    if shop_key not in shops_data:
        await interaction.response.send_message("Shop not found.")
        return
    
    item_key = item.lower().replace(" ", "_")
    currency_symbol = get_currency_symbol()
    shops_data[shop_key]["items"][item_key] = {
        "name": item,
        "price": price,
        "description": description,
        "discount": 0
    }
    save_json("shops.json", shops_data)
    await interaction.response.send_message(f"Added {item} to {shop_name} for {currency_symbol}{price}.")

@tree.command(name="shop_remove", description="Remove an item from a shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(shop_name="Name of the shop", item="Item name")
async def shop_remove(interaction: discord.Interaction, shop_name: str, item: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    item_key = item.lower().replace(" ", "_")
    
    if shop_key not in shops_data or item_key not in shops_data[shop_key]["items"]:
        await interaction.response.send_message("Shop or item not found.")
        return
    
    del shops_data[shop_key]["items"][item_key]
    save_json("shops.json", shops_data)
    await interaction.response.send_message(f"Removed {item} from {shop_name}.")

@tree.command(name="shop_edit", description="Edit an item in a shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    shop_name="Name of the shop",
    item="Item name",
    new_price="New price (optional)",
    new_description="New description (optional)"
)
async def shop_edit(interaction: discord.Interaction, shop_name: str, item: str, new_price: int = None, new_description: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    item_key = item.lower().replace(" ", "_")
    
    if shop_key not in shops_data or item_key not in shops_data[shop_key]["items"]:
        await interaction.response.send_message("Shop or item not found.")
        return
    
    if new_price is not None:
        shops_data[shop_key]["items"][item_key]["price"] = new_price
    if new_description is not None:
        shops_data[shop_key]["items"][item_key]["description"] = new_description
    
    save_json("shops.json", shops_data)
    await interaction.response.send_message(f"Updated {item} in {shop_name}.")

@tree.command(name="shop_discount", description="Set a discount on an item", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    shop_name="Name of the shop",
    item="Item name",
    discount_percent="Discount percentage (0-100)"
)
async def shop_discount(interaction: discord.Interaction, shop_name: str, item: str, discount_percent: int):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if discount_percent < 0 or discount_percent > 100:
        await interaction.response.send_message("Discount must be between 0 and 100 percent.")
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    item_key = item.lower().replace(" ", "_")
    
    if shop_key not in shops_data or item_key not in shops_data[shop_key]["items"]:
        await interaction.response.send_message("Shop or item not found.")
        return
    
    shops_data[shop_key]["items"][item_key]["discount"] = discount_percent
    save_json("shops.json", shops_data)
    await interaction.response.send_message(f"Set {discount_percent}% discount on {item} in {shop_name}.")

@tree.command(name="shop_list", description="List all shops or items in a specific shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(shop_name="Name of specific shop (optional)")
async def shop_list(interaction: discord.Interaction, shop_name: str = None):
    currency_symbol = get_currency_symbol()
    
    if shop_name is None:
        # List all shops
        if not shops_data:
            await interaction.response.send_message("No shops available.")
            return
        
        embed = discord.Embed(title="Available Shops", color=DEFAULT_EMBED_COLOR)
        for shop_key, shop_info in shops_data.items():
            embed.add_field(
                name=shop_info["name"],
                value=shop_info["description"],
                inline=False
            )
        await interaction.response.send_message(embed=embed)
    else:
        # List items in specific shop
        shop_key = shop_name.lower().replace(" ", "_")
        if shop_key not in shops_data:
            await interaction.response.send_message("Shop not found.")
            return
        
        shop_info = shops_data[shop_key]
        if not shop_info["items"]:
            await interaction.response.send_message(f"The {shop_info['name']} shop is currently empty.")
            return
        
        embed = discord.Embed(title=f"{shop_info['name']} - Items", color=DEFAULT_EMBED_COLOR)
        for item_key, item_info in shop_info["items"].items():
            original_price = item_info["price"]
            discount = item_info.get("discount", 0)
            final_price = original_price * (100 - discount) // 100
            
            price_text = f"{currency_symbol}{final_price}"
            if discount > 0:
                price_text += f" ~~{currency_symbol}{original_price}~~ ({discount}% off)"
            
            embed.add_field(
                name=f"{item_info['name']} - {price_text}",
                value=item_info["description"],
                inline=False
            )
        await interaction.response.send_message(embed=embed)

@tree.command(name="shop_buy", description="Buy an item from a shop", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(shop_name="Name of the shop", item="Item name")
async def shop_buy(interaction: discord.Interaction, shop_name: str, item: str):
    shop_key = shop_name.lower().replace(" ", "_")
    item_key = item.lower().replace(" ", "_")
    uid = str(interaction.user.id)
    ensure_user_in_stats(uid)

    if shop_key not in shops_data or item_key not in shops_data[shop_key]["items"]:
        await interaction.response.send_message("Shop or item not found.")
        return

    item_info = shops_data[shop_key]["items"][item_key]
    original_price = item_info["price"]
    discount = item_info.get("discount", 0)
    final_price = original_price * (100 - discount) // 100
    bal = user_balances.get(uid, 0)
    currency_symbol = get_currency_symbol()

    if bal < final_price:
        await interaction.response.send_message(f"You need {currency_symbol}{final_price - bal} more to buy this item.")
        return

    user_balances[uid] = bal - final_price
    
    # Add to inventory
    if shop_key not in user_inventories[uid]:
        user_inventories[uid][shop_key] = {}
    if item_key not in user_inventories[uid][shop_key]:
        user_inventories[uid][shop_key][item_key] = 0
    user_inventories[uid][shop_key][item_key] += 1
    
    save_all()
    await interaction.response.send_message(f"{interaction.user.mention} bought {item_info['name']} for {currency_symbol}{final_price}!")

# --------- Inventory and Trading -----------

@tree.command(name="inventory", description="View your inventory", guild=discord.Object(id=GUILD_ID))
@guild_only()
async def inventory(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    ensure_user_in_stats(uid)
    
    if not user_inventories[uid]:
        await interaction.response.send_message("Your inventory is empty.")
        return
    
    embed = discord.Embed(title=f"{interaction.user.display_name}'s Inventory", color=DEFAULT_EMBED_COLOR)
    
    for shop_key, items in user_inventories[uid].items():
        if shop_key in shops_data:
            shop_name = shops_data[shop_key]["name"]
            item_list = []
            for item_key, quantity in items.items():
                if item_key in shops_data[shop_key]["items"]:
                    item_name = shops_data[shop_key]["items"][item_key]["name"]
                    item_list.append(f"{item_name} x{quantity}")
            
            if item_list:
                embed.add_field(name=shop_name, value="\n".join(item_list), inline=False)
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="gift", description="Gift an item to another user", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    user="User to gift to",
    shop_name="Shop name",
    item="Item name",
    quantity="Quantity to gift"
)
async def gift(interaction: discord.Interaction, user: discord.Member, shop_name: str, item: str, quantity: int = 1):
    if quantity <= 0:
        await interaction.response.send_message("Quantity must be positive.")
        return
    
    shop_key = shop_name.lower().replace(" ", "_")
    item_key = item.lower().replace(" ", "_")
    giver_id = str(interaction.user.id)
    receiver_id = str(user.id)
    
    ensure_user_in_stats(giver_id)
    ensure_user_in_stats(receiver_id)
    
    # Check if giver has the item
    if (shop_key not in user_inventories[giver_id] or 
        item_key not in user_inventories[giver_id][shop_key] or
        user_inventories[giver_id][shop_key][item_key] < quantity):
        await interaction.response.send_message("You don't have enough of this item to gift.")
        return
    
    # Transfer items
    user_inventories[giver_id][shop_key][item_key] -= quantity
    if user_inventories[giver_id][shop_key][item_key] == 0:
        del user_inventories[giver_id][shop_key][item_key]
    
    if shop_key not in user_inventories[receiver_id]:
        user_inventories[receiver_id][shop_key] = {}
    if item_key not in user_inventories[receiver_id][shop_key]:
        user_inventories[receiver_id][shop_key][item_key] = 0
    user_inventories[receiver_id][shop_key][item_key] += quantity
    
    save_all()
    
    item_name = shops_data[shop_key]["items"][item_key]["name"] if shop_key in shops_data and item_key in shops_data[shop_key]["items"] else item
    await interaction.response.send_message(f"{interaction.user.mention} gifted {quantity}x {item_name} to {user.mention}!")

@tree.command(name="trade", description="Trade items with another user", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    user="User to trade with",
    your_shop="Your shop name",
    your_item="Your item name",
    your_quantity="Your quantity",
    their_shop="Their shop name", 
    their_item="Their item name",
    their_quantity="Their quantity"
)
async def trade(interaction: discord.Interaction, user: discord.Member, your_shop: str, your_item: str, your_quantity: int, their_shop: str, their_item: str, their_quantity: int):
    if your_quantity <= 0 or their_quantity <= 0:
        await interaction.response.send_message("Quantities must be positive.")
        return
    
    trader1_id = str(interaction.user.id)
    trader2_id = str(user.id)
    
    ensure_user_in_stats(trader1_id)
    ensure_user_in_stats(trader2_id)
    
    your_shop_key = your_shop.lower().replace(" ", "_")
    your_item_key = your_item.lower().replace(" ", "_")
    their_shop_key = their_shop.lower().replace(" ", "_")
    their_item_key = their_item.lower().replace(" ", "_")
    
    # Check if both users have their respective items
    if (your_shop_key not in user_inventories[trader1_id] or 
        your_item_key not in user_inventories[trader1_id][your_shop_key] or
        user_inventories[trader1_id][your_shop_key][your_item_key] < your_quantity):
        await interaction.response.send_message("You don't have enough of the item you're trying to trade.")
        return
    
    if (their_shop_key not in user_inventories[trader2_id] or 
        their_item_key not in user_inventories[trader2_id][their_shop_key] or
        user_inventories[trader2_id][their_shop_key][their_item_key] < their_quantity):
        await interaction.response.send_message(f"{user.mention} doesn't have enough of the item you want.")
        return
    
    # Create confirmation message
    embed = discord.Embed(title="Trade Confirmation", color=DEFAULT_EMBED_COLOR)
    embed.add_field(name="Trader 1", value=f"{interaction.user.mention}\nGiving: {your_quantity}x {your_item}", inline=True)
    embed.add_field(name="Trader 2", value=f"{user.mention}\nGiving: {their_quantity}x {their_item}", inline=True)
    embed.add_field(name="Instructions", value=f"{user.mention}, react with ✅ to accept this trade or ❌ to decline.", inline=False)
    
    message = await interaction.response.send_message(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("❌")
    
    def check(reaction, reaction_user):
        return (reaction_user == user and 
                str(reaction.emoji) in ["✅", "❌"] and 
                reaction.message.id == message.id)
    
    try:
        reaction, reaction_user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
        
        if str(reaction.emoji) == "✅":
            # Execute trade
            # Remove items from both users
            user_inventories[trader1_id][your_shop_key][your_item_key] -= your_quantity
            user_inventories[trader2_id][their_shop_key][their_item_key] -= their_quantity
            
            # Add items to both users
            if their_shop_key not in user_inventories[trader1_id]:
                user_inventories[trader1_id][their_shop_key] = {}
            if their_item_key not in user_inventories[trader1_id][their_shop_key]:
                user_inventories[trader1_id][their_shop_key][their_item_key] = 0
            user_inventories[trader1_id][their_shop_key][their_item_key] += their_quantity
            
            if your_shop_key not in user_inventories[trader2_id]:
                user_inventories[trader2_id][your_shop_key] = {}
            if your_item_key not in user_inventories[trader2_id][your_shop_key]:
                user_inventories[trader2_id][your_shop_key][your_item_key] = 0
            user_inventories[trader2_id][your_shop_key][your_item_key] += your_quantity
            
            # Clean up empty entries
            if user_inventories[trader1_id][your_shop_key][your_item_key] == 0:
                del user_inventories[trader1_id][your_shop_key][your_item_key]
            if user_inventories[trader2_id][their_shop_key][their_item_key] == 0:
                del user_inventories[trader2_id][their_shop_key][their_item_key]
            
            save_all()
            
            embed.color = 0x00FF00
            embed.clear_fields()
            embed.add_field(name="Trade Completed!", value="Both users have received their items.", inline=False)
            await message.edit(embed=embed)
        else:
            embed.color = 0xFF0000
            embed.clear_fields()
            embed.add_field(name="Trade Declined", value="The trade has been declined.", inline=False)
            await message.edit(embed=embed)
            
    except asyncio.TimeoutError:
        embed.color = 0x808080
        embed.clear_fields()
        embed.add_field(name="Trade Expired", value="The trade request has timed out.", inline=False)
        await message.edit(embed=embed)

# --------- User Profile Commands -----------

@tree.command(name="profile", description="View or customize your profile", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    bio="Your bio (optional)",
    embed_color="Hex color for your profile embed (optional)",
    msp_username="Your MSP username (optional)",
    hobbies="Your hobbies (optional)",
    dislikes="Your dislikes (optional)",
    age="Your age (optional)"
)
async def profile(interaction: discord.Interaction, bio: str = None, embed_color: str = None, msp_username: str = None, hobbies: str = None, dislikes: str = None, age: int = None):
    uid = str(interaction.user.id)
    
    if uid not in user_profiles:
        user_profiles[uid] = {}
    
    # If parameters provided, update profile
    if any([bio, embed_color, msp_username, hobbies, dislikes, age]):
        if bio:
            user_profiles[uid]["bio"] = bio
        if embed_color:
            try:
                hex_color = embed_color.lstrip('#')
                int(hex_color, 16)  # Validate hex
                user_profiles[uid]["embed_color"] = embed_color
            except ValueError:
                await interaction.response.send_message("Invalid hex color format. Please use format like #FF5733")
                return
        if msp_username:
            user_profiles[uid]["msp_username"] = msp_username
        if hobbies:
            user_profiles[uid]["hobbies"] = hobbies
        if dislikes:
            user_profiles[uid]["dislikes"] = dislikes
        if age:
            user_profiles[uid]["age"] = age
        
        save_json("user_profiles.json", user_profiles)
        await interaction.response.send_message("Profile updated successfully!")
        return
    
    # Display profile
    profile_data = user_profiles.get(uid, {})
    
    # Get embed color
    color = DEFAULT_EMBED_COLOR
    if profile_data.get("embed_color"):
        try:
            hex_color = profile_data["embed_color"].lstrip('#')
            color = int(hex_color, 16)
        except:
            pass
    
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Profile",
        color=color
    )
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
    
    if profile_data.get("bio"):
        embed.add_field(name="Bio", value=profile_data["bio"], inline=False)
    if profile_data.get("msp_username"):
        embed.add_field(name="MSP Username", value=profile_data["msp_username"], inline=True)
    if profile_data.get("age"):
        embed.add_field(name="Age", value=str(profile_data["age"]), inline=True)
    if profile_data.get("hobbies"):
        embed.add_field(name="Hobbies", value=profile_data["hobbies"], inline=False)
    if profile_data.get("dislikes"):
        embed.add_field(name="Dislikes", value=profile_data["dislikes"], inline=False)
    
    if not any(profile_data.values()):
        embed.description = "No profile information set. Use the command with parameters to customize your profile!"
    
    await interaction.response.send_message(embed=embed)

# --------- Balance Commands -----------

@tree.command(name="balance", description="Check your currency balance", guild=discord.Object(id=GUILD_ID))
@guild_only()
async def balance(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    ensure_user_in_stats(uid)
    bal = user_balances.get(uid, 0)
    currency_symbol = get_currency_symbol()
    await interaction.response.send_message(f"{interaction.user.mention}'s balance: {currency_symbol}{bal}")

@tree.command(name="balance_give", description="Give currency to a user", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(user="User to give currency to", amount="Amount to give")
async def balance_give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("Amount must be positive.")
        return
    
    uid = str(user.id)
    ensure_user_in_stats(uid)
    user_balances[uid] += amount
    save_json("balances.json", user_balances)
    currency_symbol = get_currency_symbol()
    await interaction.response.send_message(f"Gave {currency_symbol}{amount} to {user.mention}")

@tree.command(name="balance_remove", description="Remove currency from a user", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(user="User to remove currency from", amount="Amount to remove")
async def balance_remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("Amount must be positive.")
        return
    
    uid = str(user.id)
    ensure_user_in_stats(uid)
    user_balances[uid] = max(0, user_balances[uid] - amount)
    save_json("balances.json", user_balances)
    currency_symbol = get_currency_symbol()
    await interaction.response.send_message(f"Removed {currency_symbol}{amount} from {user.mention}")

# --------- Reaction Role Commands -----------

@tree.command(name="reaction_role_setup", description="Set up a reaction role message", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    title="Title of the reaction role message",
    description="Description of the reaction role message",
    channel="Channel to send the message to"
)
async def reaction_role_setup(interaction: discord.Interaction, title: str, description: str, channel: discord.TextChannel):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(title=title, description=description, color=DEFAULT_EMBED_COLOR)
    message = await channel.send(embed=embed)
    
    reaction_roles[str(message.id)] = {
        "channel_id": channel.id,
        "reactions": {}
    }
    save_json("reaction_roles.json", reaction_roles)
    
    await interaction.response.send_message(f"Reaction role message created! Message ID: {message.id}\nUse `/reaction_role_add` to add reactions and actions to this message.")

@tree.command(name="reaction_role_add", description="Add a reaction and action to a reaction role message", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    message_id="ID of the reaction role message",
    emoji="Emoji to react with (can be custom server emoji like <:name:id>)",
    action_type="Type of action to perform",
    role="Role to give (if action is role)",
    xp_amount="XP amount to give (if action is xp)",
    currency_amount="Currency amount to give (if action is currency)",
    response_message="Message to send (if action is response)"
)
@app_commands.choices(action_type=[
    app_commands.Choice(name="Give Role", value="role"),
    app_commands.Choice(name="Give XP", value="xp"),
    app_commands.Choice(name="Give Currency", value="currency"),
    app_commands.Choice(name="Send Response", value="response"),
])
async def reaction_role_add(interaction: discord.Interaction, message_id: str, emoji: str, action_type: app_commands.Choice[str], role: discord.Role = None, xp_amount: int = None, currency_amount: int = None, response_message: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if message_id not in reaction_roles:
        await interaction.response.send_message("Message ID not found in reaction role system.")
        return
    
    try:
        channel = bot.get_channel(reaction_roles[message_id]["channel_id"])
        message = await channel.fetch_message(int(message_id))
        await message.add_reaction(emoji)
    except:
        await interaction.response.send_message("Failed to add reaction to message. Make sure the message ID is correct and the emoji is valid.")
        return
    
    reaction_config = {"action": action_type.value}
    
    if action_type.value == "role" and role:
        reaction_config["role_id"] = role.id
    elif action_type.value == "xp" and xp_amount:
        reaction_config["xp_amount"] = xp_amount
    elif action_type.value == "currency" and currency_amount:
        reaction_config["currency_amount"] = currency_amount
    elif action_type.value == "response" and response_message:
        reaction_config["response_message"] = response_message
    
    reaction_roles[message_id]["reactions"][emoji] = reaction_config
    save_json("reaction_roles.json", reaction_roles)
    
    await interaction.response.send_message(f"Added reaction {emoji} with action: {action_type.name}")

# --------- Auction System -----------

@tree.command(name="auction_post", description="Post an auction item", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    name="Item name",
    server="Server location",
    rarity="Rarity type",
    type_category="Type category",
    seller="Seller to mention",
    payment_methods="Payment methods (separate with commas)",
    starting_bid="Starting bid ($1-$10, no decimals)",
    increase="Bid increase amount",
    instant_accept="Instant accept amount (with $)",
    image1="First image URL (required)",
    image2="Second image URL (optional)",
    image3="Third image URL (optional)",
    image4="Fourth image URL (optional)",
    image5="Fifth image URL (optional)",
    extra_info="Extra information (optional)",
    holds="Whether holds are accepted",
    hold_days="Number of hold days (if holds are Yes)",
    end_timestamp="Discord timestamp URL for auction end"
)
@app_commands.choices(
    server=[
        app_commands.Choice(name="US", value="US"),
        app_commands.Choice(name="UK", value="UK"),
        app_commands.Choice(name="CA", value="CA"),
        app_commands.Choice(name="TR", value="TR"),
        app_commands.Choice(name="N/A", value="N/A"),
    ],
    rarity=[
        app_commands.Choice(name="S", value="S"),
        app_commands.Choice(name="NS", value="NS"),
        app_commands.Choice(name="NA", value="NA"),
    ],
    type_category=[
        app_commands.Choice(name="EXO", value="EXO"),
        app_commands.Choice(name="OG", value="OG"),
        app_commands.Choice(name="NA", value="NA"),
    ],
    increase=[
        app_commands.Choice(name="$1", value="$1"),
        app_commands.Choice(name="$2", value="$2"),
    ],
    holds=[
        app_commands.Choice(name="Yes", value="Yes"),
        app_commands.Choice(name="No", value="No"),
        app_commands.Choice(name="Ask", value="Ask"),
    ]
)
async def auction_post(interaction: discord.Interaction, name: str, server: app_commands.Choice[str], rarity: app_commands.Choice[str], type_category: app_commands.Choice[str], seller: discord.Member, payment_methods: str, starting_bid: int, increase: app_commands.Choice[str], instant_accept: str, image1: str, image2: str = None, image3: str = None, image4: str = None, image5: str = None, extra_info: str = None, holds: app_commands.Choice[str] = None, hold_days: int = None, end_timestamp: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Validate that at least one image is provided
    if not image1:
        await interaction.response.send_message("At least one image must be provided for the auction.")
        return
    
    # Validate starting bid
    if starting_bid < 1 or starting_bid > 10:
        await interaction.response.send_message("Starting bid must be between $1 and $10.")
        return
    
    # Build the auction format
    auction_text = f"# {name}"
    
    # Add server if not N/A
    if server.value != "N/A":
        auction_text += f" ({server.value})"
    
    auction_text += " <:cutesy_star:1364222257349525506>\n"
    
    # Add rarity and type
    rarity_line = "ᯓ★ "
    if rarity.value != "NA":
        rarity_line += rarity.value
    if type_category.value != "NA":
        if rarity.value != "NA":
            rarity_line += " ‧ "
        rarity_line += type_category.value
    auction_text += rarity_line + "\n"
    
    auction_text += f"<:neonstars:1364582630363758685> ── .✦ Seller: {seller.mention}\n\n"
    
    # Payment methods
    methods_formatted = " ‧ ".join([method.strip() for method in payment_methods.split(",")])
    auction_text += f"      ✶⋆.˚ Payment Methods:\n                 {methods_formatted}\n\n"
    
    # Bidding info
    auction_text += f"╰┈➤ Starting: ${starting_bid}\n"
    auction_text += f"╰┈➤ Increase: {increase.value}\n"
    auction_text += f"╰┈➤ IA: {instant_accept}\n\n"
    
    # Extra info if provided
    if extra_info:
        auction_text += f"༘⋆ Extra Info: {extra_info}\n"
    
    # Holds info
    if holds:
        auction_text += f"𓂃 𓈒𓏸 Holds: {holds.value}"
        if holds.value == "Yes" and hold_days:
            auction_text += f"  ‧  {hold_days} Days"
        auction_text += "\n\n"
    
    # End timestamp
    if end_timestamp:
        auction_text += f"     Ends: {end_timestamp}\n\n"
    
    # Role mentions
    bidder_role = interaction.guild.get_role(BIDDER_ROLE_ID)
    buyer_role = interaction.guild.get_role(BUYER_ROLE_ID)
    
    if bidder_role and buyer_role:
        auction_text += f"{bidder_role.mention} {buyer_role.mention}"
    
    # Get forum channel
    forum_channel = bot.get_channel(AUCTION_FORUM_CHANNEL_ID)
    if not forum_channel:
        await interaction.response.send_message("Auction forum channel not found. Please check the AUCTION_FORUM_CHANNEL_ID in the config.")
        return
    
    try:
        # Create forum thread
        thread = await forum_channel.create_thread(
            name=f"Auction: {name}",
            content=auction_text
        )
        
        # Send images as separate messages
        images = [image1, image2, image3, image4, image5]
        for img_url in images:
            if img_url:
                await thread.send(img_url)
        
        # Save auction data
        auction_id = str(thread.id)
        auction_data[auction_id] = {
            "name": name,
            "server": server.value,
            "rarity": rarity.value,
            "type_category": type_category.value,
            "seller_id": seller.id,
            "starting_bid": starting_bid,
            "current_bid": starting_bid,
            "instant_accept": instant_accept,
            "thread_id": thread.id,
            "status": "active"
        }
        save_json("auctions.json", auction_data)
        
        await interaction.response.send_message(f"Auction for {name} has been posted in {thread.mention}!")
        
    except Exception as e:
        await interaction.response.send_message(f"Failed to create auction thread: {str(e)}")

# --------- Tierlist Slash Commands -----------

@tree.command(name="tierlist_post", description="Post an item to the tier list", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    item="Item name", 
    tier="Tier (S, A, B, C, D)", 
    image_url="Image URL of the item",
    custom_hex="Custom hex color (e.g., #FF5733) - optional",
    sugar_value="Sugar value - optional, manually enter if applicable",
    specifications="Specifications - optional, manually enter if applicable"
)
@app_commands.choices(tier=[
    app_commands.Choice(name="S Tier", value="s"),
    app_commands.Choice(name="A Tier", value="a"),
    app_commands.Choice(name="B Tier", value="b"),
    app_commands.Choice(name="C Tier", value="c"),
    app_commands.Choice(name="D Tier", value="d"),
])
async def tierlist_post(interaction: discord.Interaction, item: str, tier: app_commands.Choice[str], image_url: str, custom_hex: str = None, sugar_value: str = None, specifications: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    channel = bot.get_channel(TIER_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("Tier list channel not found.")
        return
    
    if custom_hex:
        try:
            hex_color = custom_hex.lstrip('#')
            color = int(hex_color, 16)
        except ValueError:
            await interaction.response.send_message("Invalid hex color format. Please use format like #FF5733 or FF5733")
            return
    else:
        color = get_color_for_tier(tier.value)

    embed = discord.Embed(title=item, color=color)
    embed.add_field(name="Tier", value=tier.value.upper(), inline=True)
    
    if sugar_value:
        embed.add_field(name="Sugar Value", value=sugar_value, inline=True)
    if specifications:
        embed.add_field(name="Specifications", value=specifications, inline=True)
    
    embed.set_image(url=image_url)

    message = await channel.send(embed=embed)

    tier_data[item.lower()] = {
        "message_id": message.id,
        "channel_id": channel.id,
        "tier": tier.value.lower(),
        "sugar_value": sugar_value if sugar_value else None,
        "specifications": specifications if specifications else None,
        "custom_hex": custom_hex if custom_hex else None,
    }
    save_json("tierlist.json", tier_data)

    response_parts = [f"Posted {item} to tier list"]
    if sugar_value:
        response_parts.append(f"with sugar value: {sugar_value}")
    if specifications:
        response_parts.append(f"with specifications: {specifications}")
    
    response_message = " ".join(response_parts) + "."
    await interaction.response.send_message(response_message)

@tree.command(name="tierlist_move", description="Move an item to a new tier", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(item="Item name", new_tier="New Tier (S, A, B, C, D)")
@app_commands.choices(new_tier=[
    app_commands.Choice(name="S Tier", value="s"),
    app_commands.Choice(name="A Tier", value="a"),
    app_commands.Choice(name="B Tier", value="b"),
    app_commands.Choice(name="C Tier", value="c"),
    app_commands.Choice(name="D Tier", value="d"),
])
async def tierlist_move(interaction: discord.Interaction, item: str, new_tier: app_commands.Choice[str]):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    key = item.lower()
    if key not in tier_data:
        await interaction.response.send_message("Item not found in tier list.")
        return
    message_id = tier_data[key]["message_id"]
    channel_id = tier_data[key]["channel_id"]
    channel = bot.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("Original channel not found.")
        return
    try:
        message = await channel.fetch_message(message_id)
    except:
        await interaction.response.send_message("Original message not found.")
        return

    embed = message.embeds[0]
    
    if tier_data[key].get("custom_hex"):
        try:
            hex_color = tier_data[key]["custom_hex"].lstrip('#')
            color = int(hex_color, 16)
        except:
            color = get_color_for_tier(new_tier.value)
    else:
        color = get_color_for_tier(new_tier.value)
    
    embed.color = color
    
    for i, field in enumerate(embed.fields):
        if field.name == "Tier":
            embed.set_field_at(i, name="Tier", value=new_tier.value.upper(), inline=True)
            break

    await message.edit(embed=embed)

    tier_data[key]["tier"] = new_tier.value.lower()
    save_json("tierlist.json", tier_data)

    await interaction.response.send_message(f"Moved {item} to {new_tier.value.upper()} tier.")

# --------- Giveaway System -----------

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.primary)
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways_data.get(self.giveaway_id)
        if not giveaway or giveaway["status"] != "active":
            await interaction.response.send_message("This giveaway is no longer active.", ephemeral=True)
            return
        
        user_id = str(interaction.user.id)
        
        # Check role restrictions
        if giveaway.get("role_restricted") and giveaway.get("required_roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            if not any(role_id in user_role_ids for role_id in giveaway["required_roles"]):
                await interaction.response.send_message("You don't have the required roles to join this giveaway.", ephemeral=True)
                return
        
        # Check level requirement
        if giveaway.get("required_level", 0) > 0:
            user_level = calculate_level(member_stats.get(user_id, {}).get("xp", 0))
            if user_level < giveaway["required_level"]:
                # Check bypass roles
                if giveaway.get("bypass_roles"):
                    user_role_ids = [role.id for role in interaction.user.roles]
                    has_bypass = any(role_id in user_role_ids for role_id in giveaway["bypass_roles"])
                    if not has_bypass:
                        await interaction.response.send_message(f"You need to be Level {giveaway['required_level']} or higher to join this giveaway.", ephemeral=True)
                        return
                else:
                    await interaction.response.send_message(f"You need to be Level {giveaway['required_level']} or higher to join this giveaway.", ephemeral=True)
                    return
        
        # Check message requirements
        if giveaway.get("required_messages", {}).get("amount", 0) > 0:
            message_type = giveaway["required_messages"]["type"]
            required_count = giveaway["required_messages"]["amount"]
            user_messages = member_stats.get(user_id, {}).get(f"{message_type}_messages", 0)
            
            if user_messages < required_count:
                # Check bypass roles
                if giveaway.get("bypass_roles"):
                    user_role_ids = [role.id for role in interaction.user.roles]
                    has_bypass = any(role_id in user_role_ids for role_id in giveaway["bypass_roles"])
                    if not has_bypass:
                        await interaction.response.send_message(f"You need {required_count} {message_type.replace('_', ' ')} messages to join this giveaway.", ephemeral=True)
                        return
                else:
                    await interaction.response.send_message(f"You need {required_count} {message_type.replace('_', ' ')} messages to join this giveaway.", ephemeral=True)
                    return
        
        # Add user to participants
        if user_id not in giveaway["participants"]:
            giveaway["participants"][user_id] = {"entries": 1}
        
        # Check for extra entries
        if giveaway.get("extra_entry_roles"):
            user_role_ids = [role.id for role in interaction.user.roles]
            for role_config in giveaway["extra_entry_roles"]:
                if role_config["role_id"] in user_role_ids:
                    giveaway["participants"][user_id]["entries"] = role_config["entries"]
                    break
        
        save_json("giveaways.json", giveaways_data)
        
        entries = giveaway["participants"][user_id]["entries"]
        entry_text = "entry" if entries == 1 else "entries"
        await interaction.response.send_message(f"You've joined the giveaway with {entries} {entry_text}!", ephemeral=True)

    @discord.ui.button(label="📊 View Participants", style=discord.ButtonStyle.secondary)
    async def view_participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways_data.get(self.giveaway_id)
        if not giveaway:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return
        
        if not giveaway["participants"]:
            await interaction.response.send_message("No participants yet.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Giveaway Participants", color=DEFAULT_EMBED_COLOR)
        
        participant_list = []
        for user_id, data in giveaway["participants"].items():
            entries = data["entries"]
            entry_text = "entry" if entries == 1 else "entries"
            participant_list.append(f"<@{user_id}> - {entries} {entry_text}")
        
        embed.description = "\n".join(participant_list[:20])  # Limit to 20 for space
        if len(participant_list) > 20:
            embed.description += f"\n... and {len(participant_list) - 20} more"
        
        embed.add_field(name="Total Participants", value=str(len(giveaway["participants"])), inline=True)
        total_entries = sum(data["entries"] for data in giveaway["participants"].values())
        embed.add_field(name="Total Entries", value=str(total_entries), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="giveaway_create", description="Create a giveaway", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(
    name="Giveaway name",
    prizes="Giveaway prizes",
    duration_hours="Duration in hours",
    winners="Number of winners",
    channel="Channel to post giveaway",
    host="Giveaway host",
    embed_color="Hex color for embed (optional)",
    role_restricted="Restrict to specific roles",
    required_level="Required level (optional)",
    required_messages_type="Required message type (optional)",
    required_messages_amount="Required message amount (optional)",
    thumbnail_url="Thumbnail URL (optional)",
    image_url="Image URL (optional)"
)
@app_commands.choices(
    role_restricted=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no"),
    ],
    required_messages_type=[
        app_commands.Choice(name="Daily", value="daily"),
        app_commands.Choice(name="Weekly", value="weekly"),
        app_commands.Choice(name="Monthly", value="monthly"),
        app_commands.Choice(name="All Time", value="all_time"),
    ]
)
async def giveaway_create(interaction: discord.Interaction, name: str, prizes: str, duration_hours: int, winners: int, channel: discord.TextChannel, host: discord.Member, embed_color: str = None, role_restricted: app_commands.Choice[str] = None, required_level: int = None, required_messages_type: app_commands.Choice[str] = None, required_messages_amount: int = None, thumbnail_url: str = None, image_url: str = None):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    import time
    import uuid
    
    giveaway_id = str(uuid.uuid4())
    end_time = int(time.time()) + (duration_hours * 3600)
    
    # Parse embed color
    color = DEFAULT_EMBED_COLOR
    if embed_color:
        try:
            hex_color = embed_color.lstrip('#')
            color = int(hex_color, 16)
        except ValueError:
            await interaction.response.send_message("Invalid hex color format.")
            return
    
    giveaway_data = {
        "id": giveaway_id,
        "name": name,
        "prizes": prizes,
        "host_id": host.id,
        "channel_id": channel.id,
        "winners": winners,
        "end_time": end_time,
        "participants": {},
        "status": "created",
        "embed_color": color,
        "role_restricted": role_restricted.value == "yes" if role_restricted else False,
        "required_roles": [],
        "extra_entry_roles": [],
        "bypass_roles": [],
        "required_level": required_level or 0,
        "required_messages": {
            "type": required_messages_type.value if required_messages_type else None,
            "amount": required_messages_amount or 0
        },
        "thumbnail_url": thumbnail_url,
        "image_url": image_url
    }
    
    giveaways_data[giveaway_id] = giveaway_data
    save_json("giveaways.json", giveaways_data)
    
    # Create test embed
    embed = discord.Embed(title=f"🎉 {name}", description=f"**Prizes:** {prizes}", color=color)
    embed.add_field(name="Host", value=host.mention, inline=True)
    embed.add_field(name="Winners", value=str(winners), inline=True)
    embed.add_field(name="Ends", value=f"<t:{end_time}:R>", inline=True)
    
    if required_level:
        embed.add_field(name="Required Level", value=str(required_level), inline=True)
    if required_messages_amount:
        embed.add_field(name="Required Messages", value=f"{required_messages_amount} {required_messages_type.value.replace('_', ' ')}", inline=True)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)
    
    embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
    
    view = GiveawayTestView(giveaway_id)
    await interaction.response.send_message(f"Giveaway created! This is a test preview that will be sent to {channel.mention}:", embed=embed, view=view)

class GiveawayTestView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=300)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🚀 Start Giveaway", style=discord.ButtonStyle.success)
    async def start_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = giveaways_data.get(self.giveaway_id)
        if not giveaway:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return
        
        channel = bot.get_channel(giveaway["channel_id"])
        if not channel:
            await interaction.response.send_message("Channel not found.", ephemeral=True)
            return
        
        # Create final embed
        embed = discord.Embed(
            title=f"🎉 {giveaway['name']}", 
            description=f"**Prizes:** {giveaway['prizes']}", 
            color=giveaway["embed_color"]
        )
        
        host = interaction.guild.get_member(giveaway["host_id"])
        embed.add_field(name="Host", value=host.mention if host else "Unknown", inline=True)
        embed.add_field(name="Winners", value=str(giveaway["winners"]), inline=True)
        embed.add_field(name="Ends", value=f"<t:{giveaway['end_time']}:R>", inline=True)
        
        if giveaway["required_level"]:
            embed.add_field(name="Required Level", value=str(giveaway["required_level"]), inline=True)
        if giveaway["required_messages"]["amount"]:
            embed.add_field(name="Required Messages", value=f"{giveaway['required_messages']['amount']} {giveaway['required_messages']['type'].replace('_', ' ')}", inline=True)
        
        if giveaway.get("thumbnail_url"):
            embed.set_thumbnail(url=giveaway["thumbnail_url"])
        if giveaway.get("image_url"):
            embed.set_image(url=giveaway["image_url"])
        
        embed.set_footer(text="Click the button below to join!")
        
        view = GiveawayView(self.giveaway_id)
        giveaway_message = await channel.send(embed=embed, view=view)
        
        giveaway["message_id"] = giveaway_message.id
        giveaway["status"] = "active"
        save_json("giveaways.json", giveaways_data)
        
        await interaction.response.edit_message(content=f"✅ Giveaway started in {channel.mention}!", embed=None, view=None)

@tree.command(name="giveaway_end", description="End a giveaway early", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(giveaway_id="Giveaway ID")
async def giveaway_end(interaction: discord.Interaction, giveaway_id: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    giveaway = giveaways_data.get(giveaway_id)
    if not giveaway:
        await interaction.response.send_message("Giveaway not found.")
        return
    
    await end_giveaway(giveaway_id, interaction.guild)
    await interaction.response.send_message("Giveaway ended!")

@tree.command(name="giveaway_reroll", description="Reroll giveaway winners", guild=discord.Object(id=GUILD_ID))
@guild_only()
@app_commands.describe(giveaway_id="Giveaway ID")
async def giveaway_reroll(interaction: discord.Interaction, giveaway_id: str):
    if not has_staff_role(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    giveaway = giveaways_data.get(giveaway_id)
    if not giveaway or giveaway["status"] != "ended":
        await interaction.response.send_message("Giveaway not found or not ended.")
        return
    
    await end_giveaway(giveaway_id, interaction.guild, reroll=True)
    await interaction.response.send_message("Giveaway rerolled!")

async def end_giveaway(giveaway_id: str, guild: discord.Guild, reroll: bool = False):
    import random
    
    giveaway = giveaways_data.get(giveaway_id)
    if not giveaway:
        return
    
    channel = guild.get_channel(giveaway["channel_id"])
    if not channel:
        return
    
    # Select winners
    if not giveaway["participants"]:
        embed = discord.Embed(
            title="🎉 Giveaway Ended",
            description=f"**{giveaway['name']}**\n\nNo participants!",
            color=0xFF0000
        )
        await channel.send(embed=embed)
        return
    
    # Create weighted list for random selection
    weighted_participants = []
    for user_id, data in giveaway["participants"].items():
        weighted_participants.extend([user_id] * data["entries"])
    
    winner_count = min(giveaway["winners"], len(giveaway["participants"]))
    winners = random.sample(weighted_participants, winner_count)
    
    # Remove duplicates while preserving order
    unique_winners = []
    seen = set()
    for winner in winners:
        if winner not in seen:
            unique_winners.append(winner)
            seen.add(winner)
    
    # Create winner announcement
    host = guild.get_member(giveaway["host_id"])
    embed = discord.Embed(
        title="🎉 Giveaway Ended!",
        description=f"**{giveaway['name']}**\n\n**Prizes:** {giveaway['prizes']}",
        color=0x00FF00
    )
    
    winner_mentions = [f"<@{winner_id}>" for winner_id in unique_winners]
    embed.add_field(name="Winners", value="\n".join(winner_mentions), inline=False)
    
    if host:
        embed.add_field(name="Host", value=host.mention, inline=True)
    
    if giveaway.get("thumbnail_url"):
        embed.set_thumbnail(url=giveaway["thumbnail_url"])
    if giveaway.get("image_url"):
        embed.set_image(url=giveaway["image_url"])
    
    action = "Rerolled" if reroll else "Ended"
    embed.set_footer(text=f"Giveaway {action}")
    
    winner_pings = " ".join(winner_mentions)
    if host:
        winner_pings += f" {host.mention}"
    
    await channel.send(content=winner_pings, embed=embed)
    
    giveaway["status"] = "ended"
    giveaway["winners_list"] = unique_winners
    save_json("giveaways.json", giveaways_data)

# --------- Event Handlers -----------

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None or message.guild.id != GUILD_ID:
        return

    # Handle verification
    if ("word" in verification_data and "role_id" in verification_data and 
        "channel_id" in verification_data and message.channel.id == verification_data["channel_id"]):
        if message.content.lower() == verification_data["word"]:
            role = message.guild.get_role(verification_data["role_id"])
            if role and role not in message.author.roles:
                await message.author.add_roles(role)
                await message.channel.send(f"{message.author.mention} has been verified!")

    # Handle sticky messages
    channel_id = str(message.channel.id)
    if channel_id in sticky_messages:
        try:
            # Delete the old sticky message
            old_message = await message.channel.fetch_message(sticky_messages[channel_id]["message_id"])
            await old_message.delete()
        except:
            pass
        
        # Send new sticky message
        sticky_data = sticky_messages[channel_id]
        if sticky_data.get("type") == "embed":
            embed = discord.Embed(
                title=sticky_data["title"],
                description=sticky_data["description"],
                color=DEFAULT_EMBED_COLOR
            )
            if sticky_data.get("image_url"):
                embed.set_image(url=sticky_data["image_url"])
            new_message = await message.channel.send(embed=embed)
        else:
            content = f"**{sticky_data['title']}**\n{sticky_data['description']}"
            if sticky_data.get("image_url"):
                content += f"\n{sticky_data['image_url']}"
            new_message = await message.channel.send(content)
        
        sticky_messages[channel_id]["message_id"] = new_message.id
        save_json("sticky_messages.json", sticky_messages)

    # Track member stats
    uid = str(message.author.id)
    ensure_user_in_stats(uid)

    # Check for level up
    old_level = calculate_level(member_stats[uid].get("xp", 0))
    
    member_stats[uid]["daily_messages"] += 1
    member_stats[uid]["weekly_messages"] += 1
    member_stats[uid]["monthly_messages"] += 1
    member_stats[uid]["all_time_messages"] += 1
    member_stats[uid]["xp"] += 5
    
    new_level = calculate_level(member_stats[uid]["xp"])
    
    # Send level up notification
    if new_level > old_level and "levelup_channel_id" in server_settings:
        levelup_channel = bot.get_channel(server_settings["levelup_channel_id"])
        if levelup_channel:
            await levelup_channel.send(f"🎉 {message.author.mention} leveled up to Level {new_level}!")

    save_all()
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or not reaction.message.guild or reaction.message.guild.id != GUILD_ID:
        return
    
    message_id = str(reaction.message.id)
    if message_id not in reaction_roles:
        return
    
    emoji = str(reaction.emoji)
    if emoji not in reaction_roles[message_id]["reactions"]:
        return
    
    config = reaction_roles[message_id]["reactions"][emoji]
    action = config["action"]
    
    uid = str(user.id)
    ensure_user_in_stats(uid)
    
    if action == "role" and "role_id" in config:
        try:
            role = reaction.message.guild.get_role(config["role_id"])
            if role and role not in user.roles:
                await user.add_roles(role)
        except:
            pass
    
    elif action == "xp" and "xp_amount" in config:
        member_stats[uid]["xp"] += config["xp_amount"]
        save_all()
    
    elif action == "currency" and "currency_amount" in config:
        user_balances[uid] += config["currency_amount"]
        save_all()
    
    elif action == "response" and "response_message" in config:
        try:
            await reaction.message.channel.send(f"{user.mention} {config['response_message']}")
        except:
            pass

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot or not reaction.message.guild or reaction.message.guild.id != GUILD_ID:
        return
    
    message_id = str(reaction.message.id)
    if message_id not in reaction_roles:
        return
    
    emoji = str(reaction.emoji)
    if emoji not in reaction_roles[message_id]["reactions"]:
        return
    
    config = reaction_roles[message_id]["reactions"][emoji]
    action = config["action"]
    
    if action == "role" and "role_id" in config:
        try:
            role = reaction.message.guild.get_role(config["role_id"])
            if role and role in user.roles:
                await user.remove_roles(role)
        except:
            pass

@tasks.loop(hours=24)
async def reset_daily():
    for uid in member_stats:
        member_stats[uid]["daily_messages"] = 0
    save_json("member_stats.json", member_stats)

@tasks.loop(hours=24*7)
async def reset_weekly():
    for uid in member_stats:
        member_stats[uid]["weekly_messages"] = 0
    save_json("member_stats.json", member_stats)

@tasks.loop(hours=24*30)
async def reset_monthly():
    for uid in member_stats:
        member_stats[uid]["monthly_messages"] = 0
    save_json("member_stats.json", member_stats)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    reset_daily.start()
    reset_weekly.start()
    reset_monthly.start()

bot.run(TOKEN)
