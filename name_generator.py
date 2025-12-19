"""
Realistic American Name Generator
Generates authentic US student names with 20,600+ combinations
"""
import random
from datetime import datetime, timedelta

FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven",
    "Andrew", "Kenneth", "Joshua", "Kevin", "Brian", "George", "Timothy", "Ronald",
    "Edward", "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon", "Benjamin", "Samuel",
    "Frank", "Gregory", "Raymond", "Alexander", "Patrick", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron", "Jose", "Adam", "Nathan", "Henry", "Douglas", "Zachary",
    "Peter", "Kyle", "Walter", "Ethan", "Jeremy", "Harold", "Keith", "Christian",
    "Roger", "Noah", "Gerald", "Carl", "Terry", "Sean", "Austin", "Arthur",
    "Lawrence", "Jesse", "Dylan", "Jordan", "Bryan", "Billy", "Joe", "Bruce",
    "Albert", "Willie", "Gabriel", "Logan", "Alan", "Juan", "Wayne", "Elijah",
    "Randy", "Roy", "Vincent", "Ralph", "Eugene", "Russell", "Bobby", "Mason",
    "Philip", "Louis", "Caleb", "Hunter", "Liam", "Owen", "Connor", "Luke"
]

FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica",
    "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley",
    "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda", "Dorothy", "Melissa",
    "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen", "Amy",
    "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
    "Samantha", "Katherine", "Christine", "Debra", "Rachel", "Carolyn", "Janet", "Catherine",
    "Maria", "Heather", "Diane", "Ruth", "Julie", "Olivia", "Joyce", "Virginia",
    "Victoria", "Kelly", "Lauren", "Christina", "Joan", "Evelyn", "Judith", "Megan",
    "Andrea", "Cheryl", "Hannah", "Jacqueline", "Martha", "Gloria", "Teresa", "Ann",
    "Sara", "Madison", "Frances", "Kathryn", "Janice", "Jean", "Abigail", "Sophia",
    "Brittany", "Isabella", "Charlotte", "Natalie", "Grace", "Alice", "Doris", "Julia",
    "Marie", "Diana", "Judy", "Danielle", "Beverly", "Denise", "Amber", "Theresa"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza",
    "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers",
    "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry", "Russell"
]

class NameGenerator:
    """Generate realistic American student names"""
    
    @staticmethod
    def generate():
        """Generate random name with gender"""
        gender = random.choice(['M', 'F'])
        first_name = random.choice(FIRST_NAMES_MALE if gender == 'M' else FIRST_NAMES_FEMALE)
        last_name = random.choice(LAST_NAMES)
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'full_name': f"{first_name} {last_name}",
            'gender': gender
        }

def generate_birth_date():
    """Generate realistic birth date for college student (18-24 years old)"""
    today = datetime.now()
    years_ago = random.randint(18, 24)
    birth_year = today.year - years_ago
    birth_month = random.randint(1, 12)
    
    # Handle February and month-end dates
    if birth_month == 2:
        birth_day = random.randint(1, 28)
    elif birth_month in [4, 6, 9, 11]:
        birth_day = random.randint(1, 30)
    else:
        birth_day = random.randint(1, 31)
    
    return f"{birth_year}-{birth_month:02d}-{birth_day:02d}"

def generate_student_email(first_name, last_name):
    """Generate realistic .edu email"""
    patterns = [
        f"{first_name.lower()}.{last_name.lower()}{random.randint(10, 99)}",
        f"{first_name.lower()}{last_name.lower()}{random.randint(100, 999)}",
        f"{first_name[0].lower()}{last_name.lower()}{random.randint(10, 99)}",
        f"{first_name.lower()}{last_name[0].lower()}{random.randint(1000, 9999)}"
    ]
    
    username = random.choice(patterns)
    
    domains = [
        "student.edu", "mail.edu", "college.edu", "university.edu",
        "stu.edu", "campus.edu", "school.edu"
    ]
    
    return f"{username}@{random.choice(domains)}"

# Test
if __name__ == "__main__":
    print("🧪 Testing Name Generator\n")
    for i in range(10):
        name = NameGenerator.generate()
        dob = generate_birth_date()
        email = generate_student_email(name['first_name'], name['last_name'])
        print(f"{i+1}. {name['full_name']:25s} | {name['gender']} | {dob} | {email}")
