/* ============================================================================
 * Blueprint registry — the vocabulary + ordered questions for each vertical.
 *
 * Adding a whole new business type = ONE entry here. Nothing else changes:
 * the prompt generator, the deterministic FSM, the simulator and the dashboard
 * all read from this registry.
 * ==========================================================================*/

import type { Blueprint, SlotDef, VerticalKey } from "./types";

const PHONE: SlotDef = {
  key: "phone",
  kind: "phone",
  ask: "Lastly, a phone number to confirm the booking?",
};
const NAME: SlotDef = {
  key: "name",
  kind: "text",
  ask: "And what name should I book this under?",
};

export const BLUEPRINTS: Record<VerticalKey, Blueprint> = {
  clinic: {
    key: "clinic",
    label: "Doctor / Clinic",
    icon: "🩺",
    noun: { booking: "appointment", customer: "patient", provider: "doctor", item: "consultation" },
    labels: { providers: "Doctors", services: "Services & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "What would you like to see us for?" },
      { key: "provider", kind: "choice", optionsFrom: "providers", ask: "Any preferred doctor, or shall I pick the next available?", optional: true },
      { key: "date", kind: "date", ask: "What date works best for you?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "What time would you prefer?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Just to confirm — a ${b.service || "consultation"} for ${b.name}${b.provider ? ` with ${b.provider}` : ""} on ${b.date} at ${b.time}. Shall I book it?`,
    done: (b) =>
      `Done! Your appointment is booked for ${b.date} at ${b.time}. You'll get a reminder the day before. Need to change it? Just message here.`,
  },

  dental: {
    key: "dental",
    label: "Dental Care",
    icon: "🦷",
    noun: { booking: "appointment", customer: "patient", provider: "dentist", item: "treatment" },
    labels: { providers: "Dentists", services: "Treatments & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "What treatment are you looking for (cleaning, filling, check-up…)?" },
      { key: "date", kind: "date", ask: "What date suits you?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And a preferred time?" },
      NAME, PHONE,
    ],
    confirm: (b) => `So that's a ${b.service} for ${b.name} on ${b.date} at ${b.time}. Confirm?`,
    done: (b) => `Booked! See you on ${b.date} at ${b.time}. A reminder will follow the day before.`,
  },

  salon: {
    key: "salon",
    label: "Salon / Spa",
    icon: "💇",
    noun: { booking: "appointment", customer: "client", provider: "stylist", item: "service" },
    labels: { providers: "Stylists", services: "Services & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "Which service would you like?" },
      { key: "provider", kind: "choice", optionsFrom: "providers", ask: "Any preferred stylist?", optional: true },
      { key: "date", kind: "date", ask: "What day works for you?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And what time?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Confirming — ${b.service} for ${b.name}${b.provider ? ` with ${b.provider}` : ""} on ${b.date} at ${b.time}. Good to go?`,
    done: (b) => `All set for ${b.date} at ${b.time}. See you then!`,
  },

  hotel: {
    key: "hotel",
    label: "Hotel / Stay",
    icon: "🏨",
    noun: { booking: "reservation", customer: "guest", provider: "room type", item: "stay" },
    labels: { providers: "Room types", services: "Room types & rates" },
    slots: [
      { key: "room", kind: "choice", optionsFrom: "providers", ask: "What type of room would you like?" },
      { key: "checkin", kind: "date", ask: "What is your check-in date?" },
      { key: "checkout", kind: "date", ask: "And your check-out date?" },
      { key: "guests", kind: "number", ask: "How many guests will be staying?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Let me confirm — a ${b.room} for ${b.guests} guest(s) under ${b.name}, checking in ${b.checkin} and out ${b.checkout}. Shall I reserve it?`,
    done: (b) => `Reserved! We look forward to hosting you from ${b.checkin}. Your confirmation will arrive shortly.`,
  },

  restaurant: {
    key: "restaurant",
    label: "Restaurant",
    icon: "🍽️",
    noun: { booking: "table booking", customer: "guest", item: "table" },
    labels: { providers: "Seating areas", services: "Menu / sittings" },
    slots: [
      { key: "guests", kind: "number", ask: "How many people is the table for?" },
      { key: "date", kind: "date", ask: "Which date?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And what time?" },
      NAME, PHONE,
    ],
    confirm: (b) => `A table for ${b.guests} under ${b.name} on ${b.date} at ${b.time}. Confirm?`,
    done: (b) => `Table booked for ${b.date} at ${b.time}. See you soon!`,
  },

  retail: {
    key: "retail",
    label: "Shop / Retail",
    icon: "🛍️",
    noun: { booking: "order", customer: "customer", item: "product" },
    labels: { providers: "Brands / aisles", services: "Products & prices" },
    slots: [
      { key: "product", kind: "choice", optionsFrom: "services", ask: "Which item are you interested in?" },
      { key: "quantity", kind: "number", ask: "How many would you like?" },
      { key: "fulfilment", kind: "fulfil", ask: "Pickup or delivery?" },
      { key: "address", kind: "text", ask: "What address should we deliver to?", dependsOn: { key: "fulfilment", equals: "delivery" } },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Confirming — ${b.quantity} x ${b.product} for ${b.name}, ${b.fulfilment}${b.address ? ` to ${b.address}` : ""}. Place the order?`,
    done: (b) =>
      `Order placed! We'll message you the moment it's ${b.fulfilment === "delivery" ? "on the way" : "ready for pickup"}.`,
  },

  travel: {
    key: "travel",
    label: "Travel / Tours",
    icon: "✈️",
    noun: { booking: "trip booking", customer: "traveller", provider: "package", item: "trip" },
    labels: { providers: "Packages / destinations", services: "Packages & prices" },
    slots: [
      { key: "package", kind: "choice", optionsFrom: "services", ask: "Which trip or package are you interested in?" },
      { key: "date", kind: "date", ask: "What is your preferred departure date?" },
      { key: "travellers", kind: "number", ask: "How many travellers?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Confirming — ${b.package} for ${b.travellers} traveller(s) under ${b.name}, departing ${b.date}. Shall I hold this for you?`,
    done: (b) => `Held! Your trip on ${b.date} is reserved. Our team will share the itinerary and payment link shortly.`,
  },

  fitness: {
    key: "fitness",
    label: "Gym / Fitness",
    icon: "🏋️",
    noun: { booking: "class booking", customer: "member", provider: "trainer", item: "session" },
    labels: { providers: "Trainers", services: "Classes & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "Which class or session would you like?" },
      { key: "provider", kind: "choice", optionsFrom: "providers", ask: "Any preferred trainer?", optional: true },
      { key: "date", kind: "date", ask: "What day works for you?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And what time?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Confirming — ${b.service} for ${b.name}${b.provider ? ` with ${b.provider}` : ""} on ${b.date} at ${b.time}. Lock it in?`,
    done: (b) => `Locked in for ${b.date} at ${b.time}. See you at the studio!`,
  },

  automotive: {
    key: "automotive",
    label: "Auto / Service",
    icon: "🚗",
    noun: { booking: "service booking", customer: "customer", provider: "service bay", item: "service" },
    labels: { providers: "Service bays", services: "Services & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "What service does your vehicle need?" },
      { key: "vehicle", kind: "text", ask: "What's the make/model of your vehicle?" },
      { key: "date", kind: "date", ask: "What date would you like to bring it in?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And a preferred drop-off time?" },
      NAME, PHONE,
    ],
    confirm: (b) =>
      `Confirming — ${b.service} for your ${b.vehicle} under ${b.name} on ${b.date} at ${b.time}. Book it?`,
    done: (b) => `Booked! Bring your vehicle in on ${b.date} at ${b.time}. We'll send a reminder the day before.`,
  },

  generic: {
    key: "generic",
    label: "General",
    icon: "📅",
    noun: { booking: "booking", customer: "customer", item: "service" },
    labels: { providers: "Providers", services: "Services & prices" },
    slots: [
      { key: "service", kind: "choice", optionsFrom: "services", ask: "What can we help you book?" },
      { key: "date", kind: "date", ask: "What date works for you?" },
      { key: "time", kind: "time", optionsFrom: "slots", ask: "And a preferred time?" },
      NAME, PHONE,
    ],
    confirm: (b) => `Confirming — ${b.service} for ${b.name} on ${b.date} at ${b.time}. Go ahead?`,
    done: (b) => `Booked for ${b.date} at ${b.time}. We'll be in touch with a reminder.`,
  },
};

export const VERTICAL_ORDER: VerticalKey[] = [
  "clinic", "dental", "salon", "hotel", "restaurant",
  "retail", "travel", "fitness", "automotive", "generic",
];
