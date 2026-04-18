This design document outlines the adaptation of Oleksandr Plyuto’s "Skeuomorph Mobile Banking" concept into a full desktop dashboard.

## **Project: Neo-Skeuomorph Desktop Banking Dashboard**

### **1. Visual Identity & Philosophy**

The design embraces **Neumorphism** (Soft UI)—a modern evolution of skeuomorphism. The interface mimics physical surfaces where elements appear to be extruded from or pressed into the background.

* **Core Aesthetic:** Soft, semi-flat, realistic lighting, and tactile depth.
* **Depth cues:** Light and shadow are the primary delimiters, replacing harsh borders.

### **2. Color Palette**

Based on the source material, the desktop view will utilize a cool, slate-blue monochrome scheme with high-contrast accents.

* **Primary Background (Surface):** `#E6EEF5` (Light Slate - *Inferred base for the Neumorphic effect*)
* **Element Surface (Cards/Buttons):** `#E6EEF5` (Same as bg, defined by shadows)
* **Shadow (Dark):** `#9CB2D0` (For the bottom-right shadow)
* **Highlight (Light):** `#FFFFFF` (For the top-left light source)
* **Text / Icons (Primary):** `#444A6C` (Deep Navy)
* **Text / Icons (Secondary):** `#788FAD` (Muted Blue-Grey)
* **Accent / Alerts:** `#D23D15` (Burnt Orange - used sparingly for notifications or negative balances)

### **3. Desktop Layout Structure**

**Grid:** 12-column fluid grid.
**View:** Three-pane dashboard layout.

#### **Zone A: Left Sidebar (Navigation)**

* **Style:** A vertical pillar running the full height, slightly recessed (pressed in) or flush with the background.
* **Logo:** Top left, embossed (raised).
* **Menu Items:**
* *Default State:* Flush text with icon.
* *Active State:* "Pressed" state (Inner shadow) to look like a clicked physical button.
* *Items:* Dashboard, My Cards, Analytics, Payments, Settings.


* **Logout:** Bottom, pill-shaped extruded button.

#### **Zone B: Main Feed (Center - 50% Width)**

* **Header:** "Good Morning, [User]" in large, dark navy typography (`#444A6C`).
* **Financial Overview (Top):**
* Large, soft-edged container showing "Total Balance".
* **Effect:** The number itself should look slightly recessed (inner shadow) into the card, like a digital clock display on a physical device.


* **Analytics Chart:**
* A line graph where the line itself is a glowing "tube" or raised ridge.
* Background grid lines are etched (inner shadow).


* **Recent Transactions:**
* A list where each transaction row is a "tile" floating slightly above the background.
* merchant logos are placed in circular, concave (pressed in) holders.



#### **Zone C: The "Wallet" Panel (Right - 25% Width)**

* **Physical Card Visualization:**
* Instead of the mobile horizontal slider, stack the user's cards vertically or show the active card in a realistic 3D render.
* **Texture:** Plastic sheen, embossed digits.


* **Quick Transfer:**
* A "num-pad" style interface or circular dial for selecting amounts.
* **Action Button:** A large, prominent circular button with a soft shadow that invites a "press."



### **4. Component Specs (CSS/Styling Logic)**

**The "Soft" Effect (Neumorphism CSS guide):**
To achieve the look on the desktop web, elements will use double box-shadows.

* **Raised Element (Buttons, Cards):**
* `box-shadow: 8px 8px 16px #9CB2D0, -8px -8px 16px #FFFFFF;`
* *Result:* Looks like it is floating or pushed up from the surface.


* **Pressed Element (Active States, Inputs, Wells):**
* `box-shadow: inset 6px 6px 10px #9CB2D0, inset -6px -6px 10px #FFFFFF;`
* *Result:* Looks like a cavity or pressed button.



**Typography:**

* **Font Family:** San Francisco (Mac) or Inter (Windows) — Clean Sans-Serif.
* **Weights:** Heavy bold for values ($), Medium for labels.

**Icons:**

* Thick stroke icons (2px or 3px).
* Color: `#444A6C` (Navy).

### **5. Key Interaction States**

1. **Hover:** The shadow spreads slightly (simulating lifting up) or glows.
2. **Click:** The shadows invert immediately from "Drop Shadow" to "Inner Shadow" to simulate the physical tactile feel of pressing a rubber button.
3. **Toggle Switches:** Realistic oval toggles that look like physical sliders.