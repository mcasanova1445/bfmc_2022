#!/usr/bin/python3
import cv2 as cv
from sqlalchemy import false
import rospy
import numpy as np
from time import sleep
import os

from automobile_data import Automobile_Data
from helper_functions import *
from PathPlanning3 import PathPlanning
from controller3 import Controller

map = cv.imread('src/models_pkg/track/materials/textures/2021_VerySmall.png')

training = False
# folder = 'training_imgs' 
folder = 'test_imgs'

# PARAMETERS
sample_time = 0.01 # [s]
max_angle = 30.0    # [deg]
max_speed = 0.5  # [m/s]
desired_speed = 0.3 # [m/s]
path_step_length = 0.01 # [m]
# CONTROLLER
k1 = 0.0 #4.0 gain error parallel to direction (speed)
k2 = 0.0 #2.0 perpedndicular error gain
k3 = 1.5 #1.5 yaw error gain
#dt_ahead = 0.5 # [s] how far into the future the curvature is estimated, feedforwarded to yaw controller
ff_curvature = 0.0 # feedforward gain
noise_std = np.deg2rad(25) # [rad] noise in the steering angle


if __name__ == '__main__':

    #init windows
    cv.namedWindow("2D-MAP", cv.WINDOW_NORMAL)
    
    # init the car data
    car = Automobile_Data(trig_control=True, trig_cam=True, trig_gps=False, trig_bno=True)

    # init trajectory
    path = PathPlanning(map) #254 463

    # init controller
    controller = Controller(k1=k1, k2=k2, k3=k3, ff=ff_curvature, folder=folder, 
                                    training=training, noise_std=noise_std)

    start_time_stamp = 0.0

    car.stop()
    os.system('rosservice call /gazebo/reset_simulation')

    try:

        while car.time_stamp < 1:
            sleep(0.1)

        start_time_stamp = car.time_stamp

        #generate path
        path_nodes = [86,436,273,136,321,262,105,350,373,451,265,145,160,353,94,127,91,99,
                        97,87,153,275,132,110,320,239,298,355,105,113,145,110,115,297,355]
        path_nodes = [86,436,273,136,321,262]
        path.generate_path_passing_through(path_nodes, path_step_length) #[86,110,310,254,463] ,[86,436, 273,136,321,262,105,350,451,265]
        # [86,436, 273,136,321,262,105,350,373,451,265,145,160,353]
        path.draw_path()
        path.print_path_info()

        # cv.waitKey(0)

        while not rospy.is_shutdown():
            tmp = np.copy(map)
            # Get the image from the camera
            frame = car.cv_image.copy()

            #draw true car position
            draw_car(tmp, car.x_true, car.y_true, car.yaw, color=(0, 255, 0))

            #FOLLOW predefined trajectory
            xd, yd, yawd, curv, finished, path_ahead, info = path.get_reference(car, desired_speed, 
                                                                                        frame=frame, training=training)
            #controller training data generation        
            controller.curr_data = [xd,yd,yawd,curv,path_ahead,info]

            if finished:
                print("Reached end of trajectory")
                car.stop()
                break
            #draw refrence car
            draw_car(tmp, xd, yd, yawd, color=(0, 0, 255))

            #car control, unrealistic: uses the true position
            if training:
                #training
                speed_ref, angle_ref, point_ahead = controller.get_control(car, path_ahead, desired_speed, curv)
                controller.save_data(frame, folder)
            else:
                #Neural network control
                action = info[2]
                speed_ref, angle_ref, net_out, point_ahead = controller.get_nn_control(frame, desired_speed, action)

            car.drive(speed=speed_ref, angle=np.rad2deg(angle_ref))

            #prints
            # clear stdout for a smoother display
            # sleep(0.05)
            os.system('cls' if os.name=='nt' else 'clear')
            print(f"x : {car.x_true:.3f}, y : {car.y_true:.3f}, yaw : {np.rad2deg(car.yaw):.3f}")
            print(f"xd: {xd:.3f}, yd: {yd:.3f}, yawd: {np.rad2deg(yawd):.3f}, curv: {curv:.3f}")
            print(f"e1: {controller.e1:.3f}, e2: {controller.e2:.3f}, e3: {np.rad2deg(controller.e3):.3f}")
            print(f"speed_ref: {speed_ref:.3f},    angle_ref: {angle_ref:.3f}")
            print(f"INFO:\nState: {info[0]}\nNext: {info[1]}\nAction: {info[2]}\nDistance: {info[3]}")
            # print(f"Coeffs:\n{coeffs}")
            print(f'Net out:\n {net_out}') if not training else None


            #project path ahead
            frame, proj = project_onto_frame(frame, car, path_ahead, color=(0,0,100)) 
            #project point ahead
            print(f"point_ahead: {point_ahead}")
            frame, proj = project_onto_frame(frame, car, point_ahead, False, color=(200, 200, 100))
            if proj is not None:
                #convert proj to cv2 point
                proj = (int(proj[0]), int(proj[1]))
                #draw line from bottmo half to proj
                cv.line(frame, (320,479), proj, (200, 200, 100), 2)

            cv.imshow("Frame preview", frame)
            cv.imshow("2D-MAP", tmp)
            cv.waitKey(1)
            rospy.sleep(0.01)
    except rospy.ROSInterruptException:
        pass
      