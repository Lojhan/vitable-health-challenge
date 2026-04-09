Right now, we only have an open agenda. what I want you to do is to investigate the codebase on how to add a provider (doctor) model, where they have their own availability based on RRULES.

all appointments should be of 1 hour to facilitate construction. so you should modify the appointment to include the provider info and the tool should check based on an asked provider their availability using RRULE matchers and overlapping. create a plan on how to build that and show me the plan before implementation with all the test cases planned to cover the new feature.

Goal:
Users should be able to ask the assistant to book an appointment with a specific provider (for example: "Book an appointment with Dr. Alice Smith"). The assistant should check the provider's availability based on their RRULE-defined schedule and existing appointments, then book the appointment if a slot is available.

What to implement:

1. Create a Provider model with fields like name, specialty, and availability (defined using RRULEs).
2. Modify the Appointment model to include a foreign key to the Provider.
3. Implement a new tool in the AI agent to list providers and their specialties.
4. Implement a new tool in the AI agent to check a provider's availability based on their RRULE-defined schedule and existing appointments.
5. Implement a new tool in the AI agent to book an appointment with a specific provider if an available slot is found.

Add seed providers to the database for testing purposes. we are not focusing on provider management features, so you can create them directly in the DB or via a simple script.

Save this prompt to .github/prompts/13-providers-scheduling.md and execute Memory Check.