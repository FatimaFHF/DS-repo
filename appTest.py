import app
import datetime

def case(method):
    print("Test Case Name:", method.__name__)
    print("Test Case Passed:", method())

# Method under test: nearest_previous_date()

date = datetime.datetime(2018, 1, 1, 0, 0, 0, 0)
date_before_within48hrs = datetime.datetime(2017, 12, 31, 23, 59, 59)
date_before_past48hrs = datetime.datetime(2017, 12, 29, 23, 59, 59)
date_after = datetime.datetime(2018, 1, 1, 0, 0, 0, 1)

def test_nearest_previous_date_givenSameDates_getDate():
    return (date == app.nearest_previous_date(date, [date]))

def test_nearest_previous_date_givenDateBefore_getDate():
    return (date_before_within48hrs == app.nearest_previous_date(date, [date_before_within48hrs]))

def test_nearest_previous_date_givenDateAfter_getNothing():
    return (None == app.nearest_previous_date(date, [date_after]))

def test_nearest_previous_date_givenDatesBefore_returnLatest():
    return (date == app.nearest_previous_date(date_after, [date_before_within48hrs, date]))

case(test_nearest_previous_date_givenSameDates_getDate)
case(test_nearest_previous_date_givenDateBefore_getDate)
case(test_nearest_previous_date_givenDateAfter_getNothing)
case(test_nearest_previous_date_givenDatesBefore_returnLatest)

# Method under test: nearest_previous_2_days()

def test_nearest_previous_2_days_givenSameDates_returnsNothing():
    return (None == app.nearest_previous_2_days(date, [date]))

def test_nearest_previous_2_days_givenDateBeforeWithin48hrs_returnsNothing():
    return (None == app.nearest_previous_2_days(date, [date_before_within48hrs]))

def test_nearest_previous_2_days_givenDateBeforePast48hrs_returnsNothing():
    return (date_before_past48hrs == app.nearest_previous_2_days(date, [date_before_past48hrs]))

def test_nearest_previous_2_days_givenDatesBeforeWithin48hrs_getNothing():
    return (None == app.nearest_previous_2_days(date_after, [date, date_before_within48hrs]))

def test_nearest_previous_2_days_givenDates_getPast48Hrs():
    return (date_before_past48hrs == app.nearest_previous_2_days(date, [date_before_within48hrs, date_before_past48hrs]))

def test_nearest_previous_2_days_givenDateAfter_returnNothing():
    return (None == app.nearest_previous_2_days(date, [date_after]))

case(test_nearest_previous_2_days_givenSameDates_returnsNothing)
case(test_nearest_previous_2_days_givenDateBeforeWithin48hrs_returnsNothing)
case(test_nearest_previous_2_days_givenDateBeforePast48hrs_returnsNothing)
case(test_nearest_previous_2_days_givenDatesBeforeWithin48hrs_getNothing)
case(test_nearest_previous_2_days_givenDates_getPast48Hrs)
case(test_nearest_previous_2_days_givenDateAfter_returnNothing)

# Methods under test: idle_car()

#def test_idle_car_givenCarIdleAtTime_returnTrue()

#def test_idle_car_givenCarIdleAtTimeLessThan48Hrs_returnFalse()

#def test_idle_car_givenCarIdleInFuture_returnFalse()

#def test_idle_car_givenCarIdleMultipleTimes_returnTrue()

