from Intent_Agent3.base import BaseAgent, Message


class StudentAgent(BaseAgent):

    def __init__(self):
        super().__init__("student_agent")

    async def handle_message(self, message: Message):
        text = message.text.lower()

        if "result" in text or "grade" in text or "marks" in text or "cgpa" in text:
            return Message(
                sender="student_agent",
                text="Academic results module is active. Please specify semester/year for detailed results."
            )

        if "syllabus" in text or "subject" in text or "course" in text or "curriculum" in text:
            return Message(
                sender="student_agent",
                text="Syllabus module is active. Please specify branch and semester."
            )

        if "timetable" in text or "schedule" in text:
            return Message(
                sender="student_agent",
                text="Timetable module is active. Please specify the day for your schedule."
            )

        if "faculty" in text or "teacher" in text or "professor" in text:
            return Message(
                sender="student_agent",
                text="Faculty information module is active."
            )

        if "attendance" in text or "present" in text:
            return Message(
                sender="student_agent",
                text="Attendance module is active. Please specify batch year for records."
            )

        if "fees" in text or "payment" in text or "tuition" in text:
            return Message(
                sender="student_agent",
                text="Fee structure module is active. Contact accounts for payment queries."
            )

        return Message(
            sender="student_agent",
            text="Student agent could not understand the request. Please be more specific."
        )
